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
    assert parsed.host in {'127.0.0.1', 'orchestra-consolidation-test-db-20261105'}
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
    assert runtime.outbox.dispatch(row_id) == 'contact_blocked'


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
