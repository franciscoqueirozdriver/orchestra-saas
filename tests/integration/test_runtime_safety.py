"""Real PostgreSQL, fake external transports; no private exports or production DSN."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

URL = os.environ.get('TEST_DATABASE_URL', '')
pytestmark = pytest.mark.skipif(not URL, reason='requires explicitly isolated PostgreSQL')
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def engine():
    parsed = make_url(URL)
    assert parsed.database == 'orchestra_consolidation_test'
    assert parsed.host in {'127.0.0.1', 'orchestra-consolidation-test-db-20261105', 'orchestra-natural-test-db-20261105'}
    engine = create_engine(URL, pool_size=12, max_overflow=8)
    with engine.begin() as c:
        c.execute(text('DROP SCHEMA public CASCADE'))
        c.execute(text('CREATE SCHEMA public'))
        c.execute(text('CREATE EXTENSION vector'))
    env = dict(os.environ, DATABASE_URL=URL, PYTHONPATH=str(ROOT / 'backend'))
    subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=ROOT / 'backend', env=env, check=True, capture_output=True)
    yield engine
    engine.dispose()


@pytest.fixture
def runtime(engine, monkeypatch):
    from app import database, locks, tasks, outbox, scheduler
    from app.models import Base, Tenant, Agent, Conversation, LLMConfig, ZapiInstance
    from app.security import encrypt_secret, hash_callback_secret
    # This fixture is scoped to the named disposable database above.
    with engine.begin() as c:
        c.execute(text('TRUNCATE ' + ','.join('"'+t.name+'"' for t in Base.metadata.sorted_tables) + ' CASCADE'))
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(database, 'engine', engine)
    monkeypatch.setattr(locks, 'engine', engine)
    monkeypatch.setattr(tasks, 'SessionLocal', factory)
    monkeypatch.setattr(outbox, 'SessionLocal', factory)
    monkeypatch.setattr(tasks.settings, 'outbound_enabled', True)
    monkeypatch.setattr(tasks.settings, 'message_group_window_seconds', 0)
    monkeypatch.setattr(tasks, '_schedule_reply', lambda *args: None)
    monkeypatch.setattr(tasks.dispatch_outbox, 'delay', lambda *a: None)
    monkeypatch.setattr(tasks.process_webhook_event, 'delay', lambda *a: None)
    def deny(*args, **kwargs):
        raise AssertionError('Unexpected external request in isolated tests')
    monkeypatch.setattr('app.zapi_client.ZapiClient._request', deny)
    monkeypatch.setattr('app.llm_client.httpx.post', deny)
    monkeypatch.setattr('app.embedding_client.httpx.post', deny)
    with factory() as db:
        db.add_all([Tenant(id='tenant-a', name='Synthetic A', slug='synthetic-a'), Tenant(id='tenant-b', name='Synthetic B', slug='synthetic-b')]);db.flush()
        db.add_all([Agent(id='agent-a', tenant_id='tenant-a', name='Synthetic agent', enabled=True, auto_reply_enabled=True), Agent(id='agent-b', tenant_id='tenant-b', name='Other agent')]);db.flush()
        db.add(LLMConfig(id='model-a', tenant_id='tenant-a', name='Synthetic', provider='openai-compatible', base_url='https://provider.invalid/v1', model='synthetic', embedding_model='synthetic', api_key_encrypted=encrypt_secret('test-only-model-key'), is_default=True));db.flush()
        db.add(ZapiInstance(id='instance-a', tenant_id='tenant-a', agent_id='agent-a', label='Synthetic', instance_id='external-a', token_encrypted=encrypt_secret('test-only-zapi-token'), callback_token_hash=hash_callback_secret('test-only-callback-secret'), sending_enabled=True, status='connected'))
        db.flush()
        db.add(Conversation(id='conversation-a', tenant_id='tenant-a', instance_id='instance-a', contact_key='synthetic-contact', status='open', revision=1, last_incoming_at=datetime.now(timezone.utc)-timedelta(minutes=1)))
        db.commit()
    return SimpleNamespace(db=factory, tasks=tasks, outbox=outbox, engine=engine, admin=SimpleNamespace(role='tenant_admin'))


def queue(runtime, *, automatic=True, key='synthetic-idempotency-key'):
    from app.models import Conversation, ZapiInstance
    with runtime.db() as db:
        row = runtime.outbox.enqueue(db, db.get(ZapiInstance, 'instance-a'), db.get(Conversation, 'conversation-a'),
                                     'synthetic response', revision=1 if automatic else None, idempotency_key=key)
        return row.id


def event(runtime, key, kind='ReceivedCallback', payload=None):
    from app.models import WebhookEvent
    with runtime.db() as db:
        row = WebhookEvent(tenant_id='tenant-a', instance_id='instance-a', event_key=key, event_type=kind,
                           payload=payload or {'phone': 'synthetic-contact', 'normalizedKind': 'text', 'normalizedText': 'synthetic question'})
        db.add(row);db.commit()
        return row.id


def test_assignment_checks_tenant_role_and_cancels_old_reply(runtime):
    from fastapi import HTTPException
    from app.routes_zapi import update_instance_policy
    from app.schemas import InstancePolicyUpdate
    from app.models import OutboxMessage, Conversation, ZapiInstance
    row_id = queue(runtime)
    with runtime.db() as db:
        with pytest.raises(HTTPException) as exc:
            update_instance_policy('instance-a', InstancePolicyUpdate(agent_id='agent-b'), db, 'tenant-a', runtime.admin)
        assert exc.value.status_code == 422
        with pytest.raises(HTTPException) as exc:
            update_instance_policy('instance-a', InstancePolicyUpdate(agent_id=None), db, 'tenant-a', SimpleNamespace(role='operator'))
        assert exc.value.status_code == 403
        update_instance_policy('instance-a', InstancePolicyUpdate(agent_id=None, messages_per_minute=3), db, 'tenant-a', runtime.admin)
    with runtime.db() as db:
        assert db.get(ZapiInstance, 'instance-a').agent_id is None
        assert db.get(Conversation, 'conversation-a').revision == 2
        assert db.get(OutboxMessage, row_id).status == 'cancelled'
    assert runtime.outbox.dispatch(row_id) == 'ignored'


def test_concurrent_duplicate_dispatch_sends_once_and_correlates_echo(runtime, monkeypatch):
    from app.models import Message, Conversation
    row_id = queue(runtime)
    entered, release = threading.Event(), threading.Event()
    calls = []
    def fake_send(*args):
        calls.append(1);entered.set();assert release.wait(10)
        return {'messageId': 'external-synthetic-message'}
    monkeypatch.setattr('app.zapi_client.ZapiClient.send_text', fake_send)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(runtime.outbox.dispatch, row_id)
        assert entered.wait(10)
        assert pool.submit(runtime.outbox.dispatch, row_id).result(timeout=5) == 'busy'
        release.set();assert first.result(timeout=10) == 'accepted'
    assert calls == [1]
    echo = event(runtime, 'external-synthetic-message', payload={'phone': 'different-lid', 'fromMe': True, 'normalizedKind': 'text', 'normalizedText': 'synthetic response'})
    assert runtime.tasks.process_webhook_event.run(echo) == 'own_echo_ignored'
    with runtime.db() as db:
        assert db.query(Message).filter_by(direction='outgoing').count() == 1
        assert db.get(Conversation, 'conversation-a').revision == 1
        assert db.query(Conversation).count() == 1


def test_unknown_send_never_retries_even_after_recovery(runtime, monkeypatch):
    from app.zapi_client import ZapiError
    from app.models import OutboxMessage
    calls = []
    def timeout(*args):
        calls.append(1)
        raise ZapiError(0)
    monkeypatch.setattr('app.zapi_client.ZapiClient.send_text', timeout)
    row_id = queue(runtime)
    assert runtime.outbox.dispatch(row_id) == 'unknown'
    runtime.tasks.recover_pending_work.run()
    assert runtime.outbox.dispatch(row_id) == 'ignored'
    assert len(calls) == 1
    with runtime.db() as db:
        assert db.get(OutboxMessage, row_id).status == 'unknown'


def test_inbound_concurrency_keeps_both_fragments_and_replay_is_idempotent(runtime):
    from app.models import Conversation, Message
    ids = [event(runtime, 'fragment-' + str(i)) for i in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(runtime.tasks.process_webhook_event.run, ids))
    # A busy durable event is picked up by recovery; retry it directly to avoid broker I/O.
    for i, result in enumerate(results):
        if result == 'busy':
            runtime.tasks.process_webhook_event.run(ids[i])
    for value in ids:
        assert runtime.tasks.process_webhook_event.run(value) == 'ignored'
    with runtime.db() as db:
        assert db.query(Message).filter_by(direction='incoming').count() == 2
        assert db.get(Conversation, 'conversation-a').revision == 3


def test_generation_is_discarded_when_configuration_changes_during_inference(runtime, monkeypatch):
    from app.models import OutboxMessage
    from app.routes_zapi import update_instance_policy
    from app.schemas import InstancePolicyUpdate
    def response(*args):
        with runtime.db() as db:
            update_instance_policy('instance-a', InstancePolicyUpdate(sending_enabled=False), db, 'tenant-a', runtime.admin)
        return 'synthetic stale answer'
    monkeypatch.setattr(runtime.tasks, '_graph_response', response)
    assert runtime.tasks.respond_to_conversation.run('tenant-a', 'conversation-a', 1) == 'stale_response'
    with runtime.db() as db:
        assert db.query(OutboxMessage).count() == 0


def test_scheduler_recovery_finds_orphans_and_does_not_steal_active_sender(runtime, monkeypatch):
    from app.models import OutboxMessage, WebhookEvent
    from app.locks import tenant_guard
    row_id = queue(runtime)
    e = event(runtime, 'orphan-event')
    with runtime.db() as db:
        row = db.get(OutboxMessage, row_id);row.status = 'dispatching';row.updated_at = datetime.now(timezone.utc)-timedelta(minutes=10);db.commit()
    queued = []
    monkeypatch.setattr(runtime.tasks.process_webhook_event, 'delay', lambda v: queued.append(v))
    with tenant_guard('tenant-a'):
        runtime.tasks.recover_pending_work.run()
        with runtime.db() as db:
            assert db.get(OutboxMessage, row_id).status == 'dispatching'
    runtime.tasks.recover_pending_work.run()
    with runtime.db() as db:
        assert db.get(OutboxMessage, row_id).status == 'unknown'
    assert e in queued


def test_second_scheduler_is_rejected_by_database_leader_lock(runtime, monkeypatch):
    from app import scheduler
    from app.locks import advisory_guard
    monkeypatch.setattr(scheduler.signal, 'signal', lambda *a: None)
    def no_child(*a, **kw):
        raise AssertionError('Follower must not start another Beat')
    monkeypatch.setattr(scheduler.subprocess, 'Popen', no_child)
    with advisory_guard('orchestra:beat-leader'):
        assert scheduler.main() == 75


def test_callbacks_are_monotonic_and_own_read_does_not_mean_customer_read(runtime, monkeypatch):
    from app.models import OutboxMessage
    monkeypatch.setattr('app.zapi_client.ZapiClient.send_text', lambda *a: {'messageId': 'external-synthetic-message'})
    row_id = queue(runtime);runtime.outbox.dispatch(row_id)
    for status in ['READ', 'SENT', 'READ_BY_ME', 'RECEIVED']:
        e = event(runtime, 'status-' + status, 'MessageStatusCallback', {'ids': ['external-synthetic-message'], 'status': status})
        runtime.tasks.process_webhook_event.run(e)
    with runtime.db() as db:
        assert db.get(OutboxMessage, row_id).status == 'read'


def test_global_pause_keeps_work_pending_without_external_effect(runtime, monkeypatch):
    from app.models import OutboxMessage
    row_id = queue(runtime)
    monkeypatch.setattr(runtime.tasks.settings, 'outbound_enabled', False)
    assert runtime.outbox.dispatch(row_id) == 'outbound_disabled'
    assert runtime.tasks.respond_to_conversation.run('tenant-a', 'conversation-a', 1) == 'outbound_disabled'
    with runtime.db() as db:
        assert db.get(OutboxMessage, row_id).status == 'pending'


@pytest.fixture
def api(runtime):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import get_db
    from app.dependencies import get_current_user
    def db_dependency():
        with runtime.db() as db:
            yield db
    app.dependency_overrides[get_db] = db_dependency
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role='tenant_admin', tenant_id='tenant-a', id='synthetic-admin')
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_ingress_auth_payload_validation_and_dedup(runtime, api):
    from app.models import WebhookEvent
    prefix = '/api/webhooks/zapi/external-a/'
    body = {'instanceId': 'external-a', 'type': 'MessageStatusCallback', 'ids': ['synthetic-message'], 'status': 'READ'}
    assert api.post(prefix + 'wrong-secret', json=body).status_code == 404
    assert api.post(prefix + 'test-only-callback-secret', json=dict(body, ids='not-a-list')).status_code == 422
    assert api.post(prefix + 'test-only-callback-secret', json=dict(body, instanceId='other-instance')).status_code == 400
    first = api.post(prefix + 'test-only-callback-secret', json=body)
    assert first.status_code == 202
    assert first.json()['duplicate'] is False
    assert api.post(prefix + 'test-only-callback-secret', json=body).json()['duplicate'] is True
    with runtime.db() as db:
        assert db.query(WebhookEvent).count() == 1


def test_callback_setup_reuses_encrypted_token_after_failure_and_accepts_grace(runtime, api, monkeypatch):
    from app.models import ZapiInstance
    from app.security import decrypt_secret, callback_secret_matches
    from app.zapi_client import ZapiError
    monkeypatch.setattr(runtime.tasks.settings, 'public_base_url', 'https://synthetic.example.invalid')
    calls = []
    def request(self, method, suffix, **kwargs):
        calls.append((method, suffix, kwargs['json']['value']))
        if len(calls) == 1:
            raise ZapiError(0)
        return {}
    monkeypatch.setattr('app.zapi_client.ZapiClient._request', request)
    path = '/api/zapi/instances/instance-a/webhooks'
    assert api.post(path).json()['configured'] is False
    assert api.post(path).json()['configured'] is True
    assert calls[0] == calls[1]
    assert calls[0][:2] == ('PUT', 'update-every-webhooks')
    with runtime.db() as db:
        instance = db.get(ZapiInstance, 'instance-a')
        token = decrypt_secret(instance.callback_token_encrypted)
        assert callback_secret_matches(instance.callback_token_hash, token)
    body = {'instanceId': 'external-a', 'type': 'ReceivedCallback', 'messageId': 'synthetic-first', 'phone': 'synthetic-contact', 'text': {'message': 'synthetic'}}
    assert api.post('/api/webhooks/zapi/external-a/' + token, json=body).status_code == 202
    assert api.post('/api/webhooks/zapi/external-a/test-only-callback-secret', json=dict(body, messageId='synthetic-second')).status_code == 202


def test_generation_duplicate_jobs_generate_and_enqueue_once(runtime, monkeypatch):
    from app.models import OutboxMessage
    entered, release = threading.Event(), threading.Event()
    calls = []
    def response(*args):
        calls.append(1); entered.set(); assert release.wait(10)
        return 'synthetic answer'
    monkeypatch.setattr(runtime.tasks, '_graph_response', response)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(runtime.tasks.respond_to_conversation.run, 'tenant-a', 'conversation-a', 1)
        assert entered.wait(10)
        assert pool.submit(runtime.tasks.respond_to_conversation.run, 'tenant-a', 'conversation-a', 1).result(timeout=5) == 'busy'
        release.set();assert first.result(timeout=10) == 'reply_queued'
    assert calls == [1]
    with runtime.db() as db:
        assert db.query(OutboxMessage).count() == 1


def test_opt_out_between_generation_and_dispatch_blocks_send(runtime):
    row_id = queue(runtime)
    e = event(runtime, 'synthetic-opt-out', payload={'phone': 'synthetic-contact', 'normalizedKind': 'text', 'normalizedText': 'Parar'})
    runtime.tasks.process_webhook_event.run(e)
    assert runtime.outbox.dispatch(row_id) == 'ignored'
    with runtime.db() as db:
        from app.models import OutboxMessage
        assert db.get(OutboxMessage,row_id).status=='cancelled'


def test_callback_arriving_before_http_ack_is_recovered_after_correlation(runtime, monkeypatch):
    from app.models import OutboxMessage
    ids = []
    def send(*args):
        e = event(runtime, 'early-callback', 'MessageStatusCallback', {'ids': ['synthetic-external'], 'status': 'READ'})
        ids.append(e)
        assert runtime.tasks.process_webhook_event.run(e) == 'busy'
        return {'messageId': 'synthetic-external'}
    monkeypatch.setattr('app.zapi_client.ZapiClient.send_text', send)
    row_id = queue(runtime)
    assert runtime.outbox.dispatch(row_id) == 'accepted'
    assert runtime.tasks.process_webhook_event.run(ids[0]) == 'message_status_updated'
    with runtime.db() as db:
        assert db.get(OutboxMessage, row_id).status == 'read'


def test_rate_limit_keeps_second_message_durable_without_sending(runtime, monkeypatch):
    from app.models import ZapiInstance, OutboxMessage
    with runtime.db() as db:
        db.get(ZapiInstance, 'instance-a').messages_per_minute = 1;db.commit()
    calls = []
    def send(*args):
        calls.append(1);return {'messageId': 'synthetic-external'}
    monkeypatch.setattr('app.zapi_client.ZapiClient.send_text', send)
    first = queue(runtime, automatic=False, key='synthetic-first-key')
    second = queue(runtime, automatic=False, key='synthetic-second-key')
    assert runtime.outbox.dispatch(first) == 'accepted'
    assert runtime.outbox.dispatch(second) == 'rate_limited'
    assert len(calls) == 1
    with runtime.db() as db:
        assert db.get(OutboxMessage, second).status == 'pending'
        assert db.get(OutboxMessage, second).next_attempt_at is not None


def test_reconnect_never_silently_enables_sending(runtime):
    from app.models import ZapiInstance
    e = event(runtime, 'synthetic-connection', 'ConnectedCallback', {'connected': True})
    runtime.tasks.process_webhook_event.run(e)
    with runtime.db() as db:
        assert db.get(ZapiInstance, 'instance-a').sending_enabled is False
        assert db.get(ZapiInstance, 'instance-a').status == 'not_checked'


def test_model_fallback_reuses_same_context_and_success_is_cached(runtime):
    from app.models import Agent, Conversation, LLMConfig, ModelRun
    from app.security import encrypt_secret, decrypt_secret
    from app.model_router import generate_with_fallback
    from app.llm_client import LLMError
    calls = []
    def client(provider, base, model, key, instructions, history, **kwargs):
        calls.append((model, instructions, list(history)))
        if model == 'synthetic':
            raise LLMError('synthetic quota', category='quota')
        return 'synthetic fallback answer'
    with runtime.db() as db:
        db.add(LLMConfig(id='model-fallback', tenant_id='tenant-a', name='Fallback', provider='openai-compatible',
                         base_url='https://provider.invalid/v1', model='synthetic-second', embedding_model='synthetic', api_key_encrypted=encrypt_secret('test-only-key')))
        agent = db.get(Agent, 'agent-a');agent.fallback_config_ids = ['model-fallback'];db.commit()
        conversation = db.get(Conversation, 'conversation-a')
        history = [{'role': 'user', 'content': 'synthetic only'}]
        assert generate_with_fallback(db, agent, conversation, 'synthetic instructions', history, client=client) == 'synthetic fallback answer'
        assert generate_with_fallback(db, agent, conversation, 'synthetic instructions', history, client=client) == 'synthetic fallback answer'
        assert len(calls) == 2
        assert calls[0][1:] == calls[1][1:]
        run = db.query(ModelRun).one()
        assert run.status == 'succeeded'
        assert 'synthetic only' in decrypt_secret(run.context_snapshot_encrypted)
        assert run.context_snapshot_encrypted.startswith('gAAAA')
        with pytest.raises(LLMError) as exc:
            generate_with_fallback(db, agent, conversation, 'different context', history, client=client)
        assert exc.value.category == 'stale_context'


def test_idempotent_enqueue_concurrently_keeps_one_row(runtime):
    from app.models import OutboxMessage
    def attempt(_):
        try:
            return queue(runtime, automatic=False, key='same-synthetic-idempotency-key')
        except ValueError:
            return 'conflict'
    with ThreadPoolExecutor(max_workers=3) as pool:
        values = list(pool.map(attempt, range(3)))
    with runtime.db() as db:
        rows = db.query(OutboxMessage).all()
        assert len(rows) == 1
        assert all(v == rows[0].id or v == 'conflict' for v in values)


def test_save_default_model_preserves_unspecified_protocol_and_disabled_state(runtime):
    from app.models import LLMConfig
    from app.routes_llm import upsert_llm_config
    from app.schemas import LLMConfigUpsert
    with runtime.db() as db:
        row = db.get(LLMConfig, 'model-a');row.protocol = 'chat-completions';row.enabled = False;row.max_output_tokens = 512;db.commit()
        upsert_llm_config(LLMConfigUpsert(provider='openai-compatible', base_url='https://provider.invalid/v1', model='synthetic'), db, 'tenant-a', runtime.admin)
    with runtime.db() as db:
        row = db.get(LLMConfig, 'model-a')
        assert row.protocol == 'chat-completions'
        assert row.enabled is False
        assert row.max_output_tokens == 512


def test_previous_callback_secret_expires_without_breaking_active_secret(runtime, api):
    from app.models import ZapiInstance
    from app.security import hash_callback_secret, encrypt_secret
    with runtime.db() as db:
        row = db.get(ZapiInstance, 'instance-a')
        row.callback_previous_hash = row.callback_token_hash
        row.callback_previous_until = datetime.now(timezone.utc)-timedelta(seconds=1)
        row.callback_token_hash = hash_callback_secret('synthetic-new-callback')
        row.callback_token_encrypted = encrypt_secret('synthetic-new-callback')
        db.commit()
    body = {'instanceId': 'external-a', 'type': 'ReceivedCallback', 'phone': 'synthetic-contact', 'messageId': 'synthetic-expiry', 'text': {'message': 'synthetic'}}
    assert api.post('/api/webhooks/zapi/external-a/test-only-callback-secret', json=body).status_code == 404
    assert api.post('/api/webhooks/zapi/external-a/synthetic-new-callback', json=body).status_code == 202


# Conversational core: all payloads below are synthetic, all external effects mocked.
def core(runtime, monkeypatch):
    from app.models import Agent, User
    from app.schemas import ConversationProfile
    with runtime.db() as db:
        db.get(Agent,'agent-a').conversation_profile=ConversationProfile(enabled=True,part_delay_seconds=0).model_dump()
        db.add(User(id='operator-a',tenant_id='tenant-a',email='operator@example.invalid',password_hash='synthetic',role='operator'))
        db.commit()
    monkeypatch.setattr(runtime.tasks.dispatch_outbox,'apply_async',lambda *a,**kw:None)
    return SimpleNamespace(id='operator-a',role='operator')


def test_core_groups_fragmented_input_and_persists_context(runtime,monkeypatch):
    from app.models import Conversation, ConversationTurn, OutboxPart
    core(runtime,monkeypatch)
    seen=[]
    monkeypatch.setattr(runtime.tasks,'_graph_response',lambda db,a,c,instructions,history,*rest: seen.append(history) or 'Horário fictício: 10h.')
    for key,body in [('first','Bom dia'),('second','qual o horário?')]:
        runtime.tasks.process_webhook_event.run(event(runtime,key,payload={'phone':'synthetic-contact','normalizedKind':'text','normalizedText':body}))
    assert runtime.tasks.respond_to_conversation.run('tenant-a','conversation-a',3)=='reply_queued'
    assert seen[0][-1]['content']=='Bom dia\nqual o horário?'
    with runtime.db() as db:
        assert len(db.query(ConversationTurn).one().message_ids)==2
        assert db.get(Conversation,'conversation-a').context_state['request']=='Bom dia\nqual o horário?'
        assert db.query(OutboxPart).count()==1
    assert runtime.tasks.respond_to_conversation.run('tenant-a','conversation-a',3)=='already_enqueued'


def test_core_cancel_and_human_commands_preempt_generation(runtime,monkeypatch):
    from app.models import Conversation, OutboxMessage, ConversationAction
    core(runtime,monkeypatch)
    queued=queue(runtime)
    runtime.tasks.process_webhook_event.run(event(runtime,'cancel-now',payload={'phone':'synthetic-contact','normalizedKind':'text','normalizedText':'Cancela'}))
    with runtime.db() as db:
        row=db.get(Conversation,'conversation-a');assert row.status=='paused' and row.pause_reason=='customer_cancel'
        assert db.get(OutboxMessage,queued).status=='cancelled'
    runtime.tasks.process_webhook_event.run(event(runtime,'new-request',payload={'phone':'synthetic-contact','normalizedKind':'text','normalizedText':'Agora quero o endereço'}))
    with runtime.db() as db:assert db.get(Conversation,'conversation-a').status=='open'
    runtime.tasks.process_webhook_event.run(event(runtime,'human',payload={'phone':'synthetic-contact','normalizedKind':'text','normalizedText':'Quero falar com uma pessoa'}))
    with runtime.db() as db:
        assert db.get(Conversation,'conversation-a').status=='human'
        assert db.query(ConversationAction).count()==2
        acknowledgment=db.query(OutboxMessage).filter_by(author_kind='system').one()
        assert 'Não tenho confirmação' in acknowledgment.content
    assert runtime.tasks.process_webhook_event.run(event(runtime,'follow-human',payload={'phone':'synthetic-contact','normalizedKind':'text','normalizedText':'Outra dúvida'}))=='stored_no_auto_reply'


def test_core_takeover_send_idempotency_and_resume_waits_for_new_input(runtime,monkeypatch):
    from app.routes_conversations import send_human,resume,takeover
    from app.schemas import ConversationSendRequest,ConversationActionRequest
    from app.models import ConversationAction, Conversation, OutboxMessage
    from fastapi import HTTPException
    operator=core(runtime,monkeypatch)
    payload=ConversationSendRequest(expected_revision=1,message='Resposta fictícia do operador',idempotency_key='synthetic-human-idempotency')
    with runtime.db() as db:
        first=send_human('conversation-a',payload,db,'tenant-a',operator)
        assert send_human('conversation-a',payload,db,'tenant-a',operator)['id']==first['id']
        assert db.query(ConversationAction).count()==1
        assert db.get(Conversation,'conversation-a').status=='human'
        assert db.get(OutboxMessage,first['id']).operator_id=='operator-a'
        with pytest.raises(HTTPException) as exc:takeover('conversation-a',ConversationActionRequest(expected_revision=1),db,'tenant-a',operator)
        assert exc.value.status_code==409
        revision=db.get(Conversation,'conversation-a').revision
        resumed=resume('conversation-a',ConversationActionRequest(expected_revision=revision),db,'tenant-a',operator)
        assert resumed['status']=='open'
        assert db.get(Conversation,'conversation-a').response_attempts==3
        assert db.get(OutboxMessage,first['id']).status=='cancelled'


def multipart(runtime,monkeypatch):
    from app.models import ZapiInstance,Conversation
    core(runtime,monkeypatch)
    with runtime.db() as db:
        return runtime.outbox.enqueue(db,db.get(ZapiInstance,'instance-a'),db.get(Conversation,'conversation-a'),'Parte um. Parte dois.',revision=1,parts=['Parte um. ','Parte dois.'],delivery_config={'delay':0}).id


def test_core_parts_send_in_order_and_callbacks_aggregate(runtime,monkeypatch):
    from app.models import OutboxMessage,OutboxPart,Message
    queued=multipart(runtime,monkeypatch);calls=[]
    def send(self,destination,content):
        calls.append(content);return {'messageId':'synthetic-part-'+str(len(calls))}
    monkeypatch.setattr('app.zapi_client.ZapiClient.send_text',send)
    assert runtime.outbox.dispatch(queued)=='part_accepted'
    first=event(runtime,'callback-1',kind='MessageStatusCallback',payload={'status':'READ','ids':['synthetic-part-1']})
    runtime.tasks.process_webhook_event.run(first)
    with runtime.db() as db:assert db.get(OutboxMessage,queued).status=='pending'
    assert runtime.outbox.dispatch(queued)=='accepted'
    assert calls==['Parte um. ','Parte dois.']
    second=event(runtime,'callback-2',kind='MessageStatusCallback',payload={'status':'READ','ids':['synthetic-part-2']})
    runtime.tasks.process_webhook_event.run(second)
    with runtime.db() as db:
        assert db.get(OutboxMessage,queued).status=='read'
        assert db.query(Message).count()==2
    echo=event(runtime,'synthetic-part-2',payload={'phone':'another-lid','fromMe':True,'normalizedKind':'text','normalizedText':'Parte dois.'})
    assert runtime.tasks.process_webhook_event.run(echo)=='own_echo_ignored'


def test_core_takeover_between_parts_preserves_first_and_cancels_rest(runtime,monkeypatch):
    from app.routes_conversations import takeover
    from app.schemas import ConversationActionRequest
    from app.models import OutboxPart
    queued=multipart(runtime,monkeypatch)
    monkeypatch.setattr('app.zapi_client.ZapiClient.send_text',lambda *a:{'messageId':'first-only'})
    assert runtime.outbox.dispatch(queued)=='part_accepted'
    with runtime.db() as db:
        takeover('conversation-a',ConversationActionRequest(expected_revision=1),db,'tenant-a',SimpleNamespace(id='operator-a',role='operator'))
        assert [p.status for p in db.query(OutboxPart).order_by(OutboxPart.ordinal)]==['accepted','cancelled']
    assert runtime.outbox.dispatch(queued)=='ignored'


def test_core_uncertain_part_stops_following_parts(runtime,monkeypatch):
    from app.zapi_client import ZapiError
    from app.models import OutboxPart
    queued=multipart(runtime,monkeypatch);calls=[]
    def timeout(*args):calls.append(1);raise ZapiError(0)
    monkeypatch.setattr('app.zapi_client.ZapiClient.send_text',timeout)
    assert runtime.outbox.dispatch(queued)=='unknown'
    runtime.tasks.recover_pending_work.run()
    assert runtime.outbox.dispatch(queued)=='ignored'
    assert calls==[1]
    with runtime.db() as db:assert [p.status for p in db.query(OutboxPart).order_by(OutboxPart.ordinal)]==['unknown','pending']


def test_core_memory_requires_approval_and_context_expires(runtime,monkeypatch):
    from app.models import MemoryItem,Conversation,Agent,LLMConfig,Message,ConversationTurn
    core(runtime,monkeypatch)
    with runtime.db() as db:
        db.add_all([MemoryItem(tenant_id='tenant-a',contact_key='synthetic-contact',content='Unreviewed private preference',approved=False),MemoryItem(tenant_id='tenant-a',contact_key='synthetic-contact',content='Approved synthetic preference',approved=True)])
        c=db.get(Conversation,'conversation-a');c.context_state={'request':'Expired synthetic question'};c.context_expires_at=datetime.now(timezone.utc)-timedelta(minutes=1)
        db.add(Message(tenant_id='tenant-a',conversation_id=c.id,direction='incoming',kind='text',content='E os de amanhã?'));db.commit()
        instructions,history=runtime.tasks._build_context(db,db.get(Agent,'agent-a'),c,[db.get(LLMConfig,'model-a')])
        assert 'Approved synthetic preference' in instructions and 'Unreviewed private preference' not in instructions
        assert 'Expired synthetic question' not in instructions
        assert db.query(ConversationTurn).one().state['previous_request']==''
        assert history[-1]['content']=='E os de amanhã?'


def test_core_continuous_input_maximum_allows_latest_revision(runtime,monkeypatch):
    from app.models import Conversation
    core(runtime,monkeypatch)
    monkeypatch.setattr(runtime.tasks.settings,'message_group_window_seconds',3)
    monkeypatch.setattr(runtime.tasks,'_graph_response',lambda *a:'Resposta fictícia')
    with runtime.db() as db:
        c=db.get(Conversation,'conversation-a');c.turn_started_at=datetime.now(timezone.utc)-timedelta(seconds=25);c.last_incoming_at=datetime.now(timezone.utc);c.revision=4;db.commit()
    assert runtime.tasks.respond_to_conversation.run('tenant-a','conversation-a',1)=='reply_queued'


def test_core_new_references_reject_cross_tenant_at_database(runtime,monkeypatch):
    from app.models import ConversationTurn,OutboxPart
    from sqlalchemy.exc import IntegrityError
    queued=multipart(runtime,monkeypatch)
    with runtime.db() as db:
        db.add(ConversationTurn(tenant_id='tenant-b',conversation_id='conversation-a',revision=99,message_ids=[],state={}))
        with pytest.raises(IntegrityError):db.commit()
        db.rollback()
        db.add(OutboxPart(tenant_id='tenant-b',outbox_id=queued,ordinal=99,content='synthetic',status='pending'))
        with pytest.raises(IntegrityError):db.commit()
        db.rollback()


def test_core_concurrent_dispatch_claims_only_one_part(runtime,monkeypatch):
    queued=multipart(runtime,monkeypatch)
    entered,release=threading.Event(),threading.Event();calls=[]
    def send(*args):calls.append(1);entered.set();assert release.wait(10);return {'messageId':'only-once'}
    monkeypatch.setattr('app.zapi_client.ZapiClient.send_text',send)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(runtime.outbox.dispatch,queued);assert entered.wait(10)
        assert pool.submit(runtime.outbox.dispatch,queued).result(timeout=5)=='busy'
        release.set();assert first.result(timeout=10)=='part_accepted'
    assert len(calls)==1


def test_core_new_input_during_inference_discards_old_parts(runtime,monkeypatch):
    from app.models import Message,Conversation,OutboxMessage
    core(runtime,monkeypatch)
    with runtime.db() as db:
        db.add(Message(tenant_id='tenant-a',conversation_id='conversation-a',direction='incoming',kind='text',content='Primeiro pedido'));db.commit()
    entered,release=threading.Event(),threading.Event()
    def infer(*args):entered.set();assert release.wait(10);return 'Resposta antiga'
    monkeypatch.setattr(runtime.tasks,'_graph_response',infer)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(runtime.tasks.respond_to_conversation.run,'tenant-a','conversation-a',1)
        assert entered.wait(10)
        runtime.tasks.process_webhook_event.run(event(runtime,'new-during-inference',payload={'phone':'synthetic-contact','normalizedKind':'text','normalizedText':'Não. Quero outra coisa'}))
        release.set();assert first.result(timeout=10)=='stale_response'
    with runtime.db() as db:assert db.query(OutboxMessage).count()==0


def test_core_profile_and_actions_enforce_role_and_company(runtime,monkeypatch):
    from app.routes_agents import save_conversation_policy
    from app.routes_conversations import takeover
    from app.schemas import ConversationProfile,ConversationActionRequest
    from fastapi import HTTPException
    core(runtime,monkeypatch)
    with runtime.db() as db:
        with pytest.raises(HTTPException) as exc:save_conversation_policy('agent-a',ConversationProfile(enabled=True),db,'tenant-a',SimpleNamespace(role='operator'))
        assert exc.value.status_code==403
        with pytest.raises(HTTPException) as exc:save_conversation_policy('agent-b',ConversationProfile(enabled=True),db,'tenant-a',runtime.admin)
        assert exc.value.status_code==404
        with pytest.raises(HTTPException) as exc:takeover('conversation-a',ConversationActionRequest(expected_revision=1),db,'tenant-b',SimpleNamespace(role='operator',id='operator-a'))
        assert exc.value.status_code==404
        with pytest.raises(HTTPException) as exc:takeover('conversation-a',ConversationActionRequest(expected_revision=1),db,'tenant-a',SimpleNamespace(role='viewer',id='operator-a'))
        assert exc.value.status_code==403


def test_core_schema_downgrade_refuses_new_data(runtime,monkeypatch):
    from app.models import ConversationTurn
    core(runtime,monkeypatch)
    with runtime.db() as db:
        db.add(ConversationTurn(tenant_id='tenant-a',conversation_id='conversation-a',revision=1,message_ids=[],state={}));db.commit()
    env=dict(os.environ,DATABASE_URL=URL,PYTHONPATH=str(ROOT/'backend'))
    result=subprocess.run([sys.executable,'-m','alembic','downgrade','0004_model_run_uniqueness'],cwd=ROOT/'backend',env=env,capture_output=True,text=True)
    assert result.returncode!=0 and 'Downgrade recusado' in result.stderr
    with runtime.db() as db:
        assert db.execute(text('SELECT version_num FROM alembic_version')).scalar()=='0005_conversation_core'
        assert db.query(ConversationTurn).count()==1


def test_core_resume_keeps_recent_operator_words_without_restoring_old_filters(runtime,monkeypatch):
    from app.models import Message,Conversation
    from app.routes_conversations import send_human,resume
    from app.schemas import ConversationSendRequest,ConversationActionRequest
    operator=core(runtime,monkeypatch)
    monkeypatch.setattr('app.zapi_client.ZapiClient.send_text',lambda *args:{'messageId':'human-accepted'})
    with runtime.db() as db:
        row=send_human('conversation-a',ConversationSendRequest(expected_revision=1,message='Condição fictícia explicada pelo operador',idempotency_key='operator-history-test-key'),db,'tenant-a',operator)
    assert runtime.outbox.dispatch(row['id'])=='accepted'
    with runtime.db() as db:
        c=db.get(Conversation,'conversation-a');c.context_state={'request':'Filtro antigo fictício'};db.commit()
        resume(c.id,ConversationActionRequest(expected_revision=c.revision),db,'tenant-a',operator)
    runtime.tasks.process_webhook_event.run(event(runtime,'after-human',payload={'phone':'synthetic-contact','normalizedKind':'text','normalizedText':'E o prazo?'}))
    seen=[]
    monkeypatch.setattr(runtime.tasks,'_graph_response',lambda db,a,c,i,h,*rest:seen.append((i,h)) or 'Resposta fictícia sem executar ações')
    with runtime.db() as db:revision=db.get(Conversation,'conversation-a').revision
    assert runtime.tasks.respond_to_conversation.run('tenant-a','conversation-a',revision)=='reply_queued'
    assert any('Mensagem de operador' in m['content'] for m in seen[0][1])
    assert 'Filtro antigo fictício' not in seen[0][0]


def test_core_optional_presence_failure_never_prevents_text(runtime,monkeypatch):
    from app.models import OutboxMessage
    from app.transport import Receipt
    queued=multipart(runtime,monkeypatch);calls=[]
    with runtime.db() as db:
        db.get(OutboxMessage,queued).delivery_config={'delay':0,'presence':True};db.commit()
    class FakeTransport:
        def composing(self,*args):raise RuntimeError('Synthetic presence failure')
        def send_text(self,*args):calls.append(1);return Receipt('synthetic-presence-id')
    monkeypatch.setattr(runtime.outbox,'for_instance',lambda _:FakeTransport())
    assert runtime.outbox.dispatch(queued)=='part_accepted'
    assert calls==[1]


def test_core_rate_limit_counts_parts_not_only_parent(runtime,monkeypatch):
    from app.models import ZapiInstance,OutboxPart
    queued=multipart(runtime,monkeypatch)
    with runtime.db() as db:db.get(ZapiInstance,'instance-a').messages_per_minute=1;db.commit()
    monkeypatch.setattr('app.zapi_client.ZapiClient.send_text',lambda *a:{'messageId':'only-one-per-minute'})
    assert runtime.outbox.dispatch(queued)=='part_accepted'
    assert runtime.outbox.dispatch(queued)=='rate_limited'
    with runtime.db() as db:assert [p.attempts for p in db.query(OutboxPart).order_by(OutboxPart.ordinal)]==[1,0]


def test_core_recovery_marks_abandoned_part_unknown(runtime,monkeypatch):
    from app.models import OutboxMessage,OutboxPart
    queued=multipart(runtime,monkeypatch)
    with runtime.db() as db:
        parent=db.get(OutboxMessage,queued);parent.status='dispatching';parent.updated_at=datetime.now(timezone.utc)-timedelta(minutes=3)
        db.query(OutboxPart).filter_by(outbox_id=queued,ordinal=0).one().status='dispatching';db.commit()
    runtime.tasks.recover_pending_work.run()
    with runtime.db() as db:
        assert db.get(OutboxMessage,queued).status=='unknown'
        assert db.query(OutboxPart).filter_by(outbox_id=queued,ordinal=0).one().status=='unknown'
    assert runtime.outbox.dispatch(queued)=='ignored'


def test_provider_connections_are_multiple_private_and_tenant_scoped(runtime):
    from app.routes_llm import create_connection,list_connections,update_connection,delete_connection
    from app.schemas import LLMConfigUpsert
    from app.models import LLMConfig
    from app.security import decrypt_secret
    from fastapi import HTTPException
    payload=LLMConfigUpsert(name='Gemini synthetic',provider='gemini',protocol='gemini',base_url='https://generativelanguage.googleapis.com/v1beta',model='synthetic',api_key='synthetic-private-key')
    with runtime.db() as db:
        created=create_connection(payload,db,'tenant-a',runtime.admin)
        assert len(list_connections(db,'tenant-a'))==2
        assert list_connections(db,'tenant-b')==[]
        assert not created['is_default'] and created['resolved_protocol']=='gemini'
        assert 'synthetic-private-key' not in str(created)
        stored=db.get(LLMConfig,created['id']);assert decrypt_secret(stored.api_key_encrypted)=='synthetic-private-key'
        updated=update_connection(created['id'],LLMConfigUpsert(name='Renamed',provider='gemini',protocol='gemini',base_url=payload.base_url,model='new-synthetic'),db,'tenant-a',runtime.admin)
        assert updated['name']=='Renamed' and updated['has_api_key']
        assert decrypt_secret(db.get(LLMConfig,created['id']).api_key_encrypted)=='synthetic-private-key'
        with pytest.raises(HTTPException) as exc:update_connection(created['id'],payload,db,'tenant-b',runtime.admin)
        assert exc.value.status_code==404
        with pytest.raises(HTTPException) as exc:create_connection(payload,db,'tenant-a',SimpleNamespace(role='operator'))
        assert exc.value.status_code==403
        delete_connection(created['id'],db,'tenant-a',runtime.admin)
        assert len(list_connections(db,'tenant-a'))==1


def test_generation_provider_change_preserves_embedding_destination_and_old_key(runtime):
    from app.routes_llm import update_connection
    from app.schemas import LLMConfigUpsert
    from app.models import LLMConfig,KnowledgeDocument
    from app.security import decrypt_secret
    with runtime.db() as db:
        db.add(KnowledgeDocument(tenant_id='tenant-a',filename='synthetic.txt',status='indexed'));db.commit()
        update_connection('model-a',LLMConfigUpsert(provider='gemini',protocol='gemini',base_url='https://generativelanguage.googleapis.com/v1beta',model='synthetic',api_key='synthetic-new-google-key'),db,'tenant-a',runtime.admin)
        row=db.get(LLMConfig,'model-a')
        assert row.embedding_base_url=='https://provider.invalid/v1'
        assert row.embedding_model=='synthetic'
        assert decrypt_secret(row.embedding_api_key_encrypted)=='test-only-model-key'
        assert decrypt_secret(row.api_key_encrypted)=='synthetic-new-google-key'


def test_connection_move_requires_new_key_and_never_changes_rejected_config(runtime):
    from app.routes_llm import update_connection
    from app.schemas import LLMConfigUpsert
    from app.models import LLMConfig,KnowledgeDocument
    from fastapi import HTTPException
    with runtime.db() as db:
        payload=LLMConfigUpsert(provider='custom',base_url='https://other.invalid/v1',model='synthetic')
        with pytest.raises(HTTPException) as exc:update_connection('model-a',payload,db,'tenant-a',runtime.admin)
        assert exc.value.status_code==422
        assert db.get(LLMConfig,'model-a').base_url=='https://provider.invalid/v1'
        db.add(KnowledgeDocument(tenant_id='tenant-a',filename='synthetic.txt',status='indexed'));db.commit()
        payload=LLMConfigUpsert(provider='custom',base_url='https://provider.invalid/v1',model='synthetic',embedding_base_url='https://other.invalid/v1',embedding_api_key='synthetic-new-key')
        with pytest.raises(HTTPException) as exc:update_connection('model-a',payload,db,'tenant-a',runtime.admin)
        assert exc.value.status_code==409
        db.expire_all();assert db.get(LLMConfig,'model-a').embedding_base_url is None


def test_agent_models_keep_fallback_order_and_refuse_effective_default_duplicates(runtime):
    from app.models import Agent,LLMConfig
    from app.routes_agents import update_agent
    from app.routes_llm import make_default,delete_connection
    from app.schemas import AgentUpdate
    from app.security import encrypt_secret
    from app.model_router import candidate_configs
    from fastapi import HTTPException
    with runtime.db() as db:
        for identifier in ['alternative-1','alternative-2']:
            db.add(LLMConfig(id=identifier,tenant_id='tenant-a',provider='custom',base_url='https://synthetic.invalid/v1',model=identifier,api_key_encrypted=encrypt_secret('synthetic-key')))
        db.commit()
        update_agent('agent-a',AgentUpdate(llm_config_id='model-a',fallback_config_ids=['alternative-2','alternative-1']),db,'tenant-a',runtime.admin)
        assert [c.id for c in candidate_configs(db,db.get(Agent,'agent-a'))]==['model-a','alternative-2','alternative-1']
        with pytest.raises(HTTPException) as exc:delete_connection('alternative-1',db,'tenant-a',runtime.admin)
        assert exc.value.status_code==409
        with pytest.raises(HTTPException) as exc:update_agent('agent-a',AgentUpdate(llm_config_id=None,fallback_config_ids=['model-a']),db,'tenant-a',runtime.admin)
        assert exc.value.status_code==422
        update_agent('agent-a',AgentUpdate(llm_config_id=None,fallback_config_ids=['alternative-1']),db,'tenant-a',runtime.admin)
        with pytest.raises(HTTPException) as exc:make_default('alternative-1',db,'tenant-a',runtime.admin)
        assert exc.value.status_code==409


def test_default_change_does_not_mix_indexed_embedding_spaces(runtime):
    from app.models import KnowledgeDocument,LLMConfig
    from app.routes_llm import create_connection,make_default
    from app.schemas import LLMConfigUpsert
    from fastapi import HTTPException
    with runtime.db() as db:
        db.add(KnowledgeDocument(tenant_id='tenant-a',filename='synthetic.txt',status='indexed'));db.commit()
        other=create_connection(LLMConfigUpsert(name='Other',provider='custom',protocol='responses',base_url='https://other.invalid/v1',model='synthetic',api_key='synthetic-key'),db,'tenant-a',runtime.admin)
        with pytest.raises(HTTPException) as exc:make_default(other['id'],db,'tenant-a',runtime.admin)
        assert exc.value.status_code==409
        assert db.get(LLMConfig,'model-a').is_default is True
