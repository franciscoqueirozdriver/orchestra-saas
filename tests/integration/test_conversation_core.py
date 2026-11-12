from datetime import datetime, timezone

import pytest

from .conftest import URL


@pytest.fixture(autouse=True)
def graph_checkpointer_database(runtime, monkeypatch):
    # The response graph checkpoints through its own psycopg connection; keep it
    # on the isolated disposable database instead of the ambient default DSN.
    from langgraph.checkpoint.postgres import PostgresSaver
    monkeypatch.setattr(runtime.tasks.settings, 'database_url', URL)
    conninfo = URL.replace('postgresql+psycopg://', 'postgresql://', 1)
    # LangGraph setup builds indexes CONCURRENTLY, which waits on idle
    # transactions; prepare the schema before any test session is open.
    with PostgresSaver.from_conn_string(conninfo) as checkpointer:
        checkpointer.setup()
    monkeypatch.setattr(runtime.tasks, '_checkpointer_ready', True)


def _enable(runtime, **profile):
    from app.models import Agent
    with runtime.db() as db:
        agent = db.get(Agent, 'agent-a')
        agent.conversation_profile = {'enabled': True, **profile}
        db.commit()


def _add_incoming(runtime, content):
    from app.models import Message
    with runtime.db() as db:
        db.add(Message(tenant_id='tenant-a', conversation_id='conversation-a',
                       external_id=None, direction='incoming', kind='text',
                       content=content, status='received', author_kind='user'))
        db.commit()


def test_structured_decision_is_applied_only_on_current_revision(runtime, monkeypatch):
    from app.models import Conversation
    _enable(runtime, structured_decision_enabled=True, memory_enabled=True)
    monkeypatch.setattr(runtime.tasks, 'generate_with_fallback', lambda *a, **k: (
        '{"reply":"Claro, Ana. Qual o bairro?",'
        '"decision":{"intent":"pedido","sentiment":"neutro","stage":"coletando",'
        '"action":"respond","facts":{"interlocutor_name":"Ana"},'
        '"pending":["confirmar bairro"],"next_best_action":"perguntar bairro"}}'))
    result = runtime.tasks.respond_to_conversation('tenant-a', 'conversation-a', 1)
    assert result == 'reply_queued'
    with runtime.db() as db:
        conversation = db.get(Conversation, 'conversation-a')
        assert conversation.context_state['intent'] == 'pedido'
        assert conversation.context_state['pending'] == ['confirmar bairro']


def test_flags_off_keep_plain_text_pipeline(runtime, monkeypatch):
    from app.models import Conversation, OutboxMessage
    _enable(runtime)
    monkeypatch.setattr(runtime.tasks, 'generate_with_fallback',
                        lambda *a, **k: 'Resposta comum em texto.')
    result = runtime.tasks.respond_to_conversation('tenant-a', 'conversation-a', 1)
    assert result == 'reply_queued'
    with runtime.db() as db:
        conversation = db.get(Conversation, 'conversation-a')
        assert 'intent' not in conversation.context_state
        sent = db.query(OutboxMessage).filter_by(tenant_id='tenant-a',
                                                 conversation_id='conversation-a').one()
        assert sent.content == 'Resposta comum em texto.'
        assert sent.author_kind == 'assistant'


def test_invalid_envelope_never_reaches_outbox_and_escalates(runtime, monkeypatch):
    from app.models import Conversation, OutboxMessage
    _enable(runtime, structured_decision_enabled=True)
    monkeypatch.setattr(runtime.tasks, 'generate_with_fallback',
                        lambda *a, **k: 'Resposta comum sem o envelope exigido.')
    result = runtime.tasks.respond_to_conversation('tenant-a', 'conversation-a', 1)
    assert result == 'intervention_requested'
    with runtime.db() as db:
        conversation = db.get(Conversation, 'conversation-a')
        assert conversation.status == 'human'
        assert conversation.pause_reason == 'intervention_requested'
        rows = db.query(OutboxMessage).filter_by(tenant_id='tenant-a',
                                                 conversation_id='conversation-a').all()
        assert len(rows) == 1 and rows[0].author_kind == 'system'
        assert 'Resposta comum sem o envelope exigido.' not in rows[0].content


def test_handoff_decision_requests_human_and_enqueues_agent_reply(runtime, monkeypatch):
    from app.models import Conversation, InterventionRequest, OutboxMessage
    _enable(runtime, structured_decision_enabled=True)
    reply = 'Vou chamar uma pessoa da equipe para continuar.'
    monkeypatch.setattr(runtime.tasks, 'generate_with_fallback', lambda *a, **k: (
        '{"reply":"' + reply + '","decision":{"intent":"humano","sentiment":"urgente",'
        '"stage":"handoff","action":"handoff","facts":{},"pending":[],'
        '"next_best_action":"chamar equipe"}}'))
    result = runtime.tasks.respond_to_conversation('tenant-a', 'conversation-a', 1)
    assert result == 'handoff_requested'
    with runtime.db() as db:
        conversation = db.get(Conversation, 'conversation-a')
        assert conversation.status == 'human'
        assert conversation.pause_reason == 'human_requested'
        assert db.query(InterventionRequest).filter_by(
            tenant_id='tenant-a', conversation_id='conversation-a').count() == 1
        sent = db.query(OutboxMessage).filter_by(tenant_id='tenant-a',
                                                 conversation_id='conversation-a').one()
        assert sent.content == reply and sent.author_kind == 'assistant'


def test_structured_turn_injects_business_memory_and_records_provenance(runtime, monkeypatch):
    from app.models import BusinessProfile, Conversation, MemoryItem, Message
    _enable(runtime, structured_decision_enabled=True, memory_enabled=True)
    _add_incoming(runtime, 'Meu nome é Ana e prefiro de manhã.')
    seen = []
    with runtime.db() as db:
        db.add(BusinessProfile(tenant_id='tenant-a', data={'name': 'Empresa Sintética'}))
        db.add(MemoryItem(tenant_id='tenant-a', contact_key='synthetic-contact',
                          kind='preference', fact_key='preference', content='prefere manhã',
                          approved=True, source='operator', source_message_id='seed-message',
                          last_seen_at=datetime.now(timezone.utc)))
        db.commit()
        incoming_id = db.query(Message).filter_by(direction='incoming').one().id
    def fake(*args, **kwargs):
        seen.append(args[3])
        return ('{"reply":"Claro, Ana. Qual o bairro?",'
                '"decision":{"intent":"pedido","sentiment":"neutro","stage":"coletando",'
                '"action":"respond","facts":{"interlocutor_name":"Ana"},'
                '"pending":[],"next_best_action":"perguntar bairro"}}')
    monkeypatch.setattr(runtime.tasks, 'generate_with_fallback', fake)
    assert runtime.tasks.respond_to_conversation('tenant-a', 'conversation-a', 1) == 'reply_queued'
    assert 'Empresa Sintética' in seen[0]
    assert 'prefere manhã' in seen[0] and 'Fatos da conversa' in seen[0]
    with runtime.db() as db:
        fact = db.query(MemoryItem).filter_by(tenant_id='tenant-a', fact_key='interlocutor_name').one()
        assert fact.content == 'Ana'
        assert fact.approved is True
        assert fact.source_message_id == incoming_id
        conversation = db.get(Conversation, 'conversation-a')
        assert conversation.context_state['recent_openings'] == ['Claro, Ana. Qual o bairro?']


def test_wait_action_skips_outbox(runtime, monkeypatch):
    from app.models import Conversation, OutboxMessage
    _enable(runtime, structured_decision_enabled=True)
    _add_incoming(runtime, 'ok')
    monkeypatch.setattr(runtime.tasks, 'generate_with_fallback', lambda *a, **k: (
        '{"reply":"Combinado.","decision":{"intent":"confirmacao","sentiment":"positivo",'
        '"stage":"encerrado","action":"wait","facts":{},"pending":[],'
        '"next_best_action":"nada"}}'))
    with runtime.db() as db:
        conversation = db.get(Conversation, 'conversation-a')
        conversation.context_state = {}
        conversation.turn_started_at = conversation.last_incoming_at
        db.commit()
        before = db.query(OutboxMessage).filter_by(tenant_id='tenant-a',
                                                   conversation_id='conversation-a').count()
    result = runtime.tasks.respond_to_conversation('tenant-a', 'conversation-a', 1)
    assert result == 'wait_skipped'
    with runtime.db() as db:
        after = db.query(OutboxMessage).filter_by(tenant_id='tenant-a',
                                                  conversation_id='conversation-a').count()
    assert after == before


def test_wait_skipped_is_terminal_for_recovery(runtime, monkeypatch):
    from app.models import Conversation, OutboxMessage
    _enable(runtime, structured_decision_enabled=True)
    _add_incoming(runtime, 'ok')
    monkeypatch.setattr(runtime.tasks, 'generate_with_fallback', lambda *a, **k: (
        '{"reply":"Combinado.","decision":{"intent":"confirmacao","sentiment":"positivo",'
        '"stage":"encerrado","action":"wait","facts":{},"pending":[],'
        '"next_best_action":"nada"}}'))
    with runtime.db() as db:
        conversation = db.get(Conversation, 'conversation-a')
        conversation.context_state = {}
        conversation.turn_started_at = conversation.last_incoming_at
        db.commit()
        revision = conversation.revision
    scheduled = []
    monkeypatch.setattr(runtime.tasks, '_schedule_reply', lambda *args: scheduled.append(args))
    assert runtime.tasks.respond_to_conversation('tenant-a', 'conversation-a', revision) == 'wait_skipped'
    with runtime.db() as db:
        conversation = db.get(Conversation, 'conversation-a')
        assert conversation.response_attempts >= 3
        assert conversation.revision == revision
        assert db.query(OutboxMessage).filter_by(tenant_id='tenant-a',
                                                 conversation_id='conversation-a',
                                                 response_revision=revision).count() == 0
    runtime.tasks.recover_pending_work.run()
    assert scheduled == []


def test_stale_handoff_never_mutates_conversation(runtime):
    from app.models import Conversation, InterventionRequest, OutboxMessage
    _enable(runtime, structured_decision_enabled=True)
    with runtime.db() as db:
        assert runtime.tasks._handoff_from_decision(
            db, 'tenant-a', 'conversation-a', 2, 'agent-a',
            'Vou chamar uma pessoa da equipe.') == 'stale_response'
        assert runtime.tasks._handoff_from_decision(
            db, 'tenant-a', 'conversation-a', 1, 'agent-b',
            'Vou chamar uma pessoa da equipe.') == 'stale_response'
        db.expire_all()
        conversation = db.get(Conversation, 'conversation-a')
        assert conversation.revision == 1
        assert conversation.status == 'open'
        assert db.query(InterventionRequest).count() == 0
        assert db.query(OutboxMessage).count() == 0


def test_summary_updates_context_without_changing_revision(runtime, monkeypatch):
    from app.models import Conversation

    _enable(runtime, memory_enabled=True)
    for index in range(8):
        _add_incoming(runtime, f'mensagem {index}')
    monkeypatch.setattr(runtime.tasks, 'complete', lambda *a, **k: 'Resumo fictício do atendimento.')
    result = runtime.tasks.summarize_conversation.run('tenant-a', 'conversation-a', 1)
    assert result == 'summarized'
    with runtime.db() as db:
        conversation = db.get(Conversation, 'conversation-a')
        assert conversation.context_state['summary'] == 'Resumo fictício do atendimento.'
        assert conversation.context_state['summary_cursor']
        assert conversation.revision == 1


def test_summary_is_skipped_when_revision_is_stale(runtime, monkeypatch):
    _enable(runtime, memory_enabled=True)
    monkeypatch.setattr(runtime.tasks, 'complete', lambda *a, **k: 'não deveria ser chamado')
    result = runtime.tasks.summarize_conversation.run('tenant-a', 'conversation-a', 2)
    assert result == 'stale'


def test_memory_and_decision_routes_never_cross_tenants(runtime):
    from fastapi import HTTPException

    from app import routes_memory
    from app.models import MemoryItem
    from app.schemas import MemoryUpdate

    with runtime.db() as db:
        db.add(MemoryItem(id='memory-a', tenant_id='tenant-a', contact_key='synthetic-contact',
                          kind='note', content='fato do tenant A'))
        db.commit()
        calls = (
            lambda: routes_memory.read_memory('conversation-a', db=db, tenant_id='tenant-b'),
            lambda: routes_memory.read_decision('conversation-a', db=db, tenant_id='tenant-b'),
            lambda: routes_memory.update_memory('memory-a', payload=MemoryUpdate(approved=True),
                                                db=db, tenant_id='tenant-b', user=runtime.admin),
            lambda: routes_memory.delete_memory('memory-a', db=db, tenant_id='tenant-b',
                                                user=runtime.admin),
        )
        for call in calls:
            with pytest.raises(HTTPException) as failure:
                call()
            assert failure.value.status_code == 404
        assert db.get(MemoryItem, 'memory-a') is not None


def test_read_memory_returns_summary_pending_and_facts(runtime):
    from app import routes_memory
    from app.models import Conversation, MemoryItem

    with runtime.db() as db:
        conversation = db.get(Conversation, 'conversation-a')
        conversation.context_state = {'summary': 'Resumo atual.', 'pending': ['bairro']}
        db.add(MemoryItem(id='memory-a', tenant_id='tenant-a', contact_key='synthetic-contact',
                          kind='preference', fact_key='preference', content='prefere manhã',
                          approved=True, source='operator'))
        db.commit()
        payload = routes_memory.read_memory('conversation-a', db=db, tenant_id='tenant-a')
    assert payload['summary'] == 'Resumo atual.'
    assert payload['pending'] == ['bairro']
    assert [item['content'] for item in payload['items']] == ['prefere manhã']
    assert 'tenant_id' not in payload['items'][0]
    assert payload['items'][0]['approved'] is True


def test_update_and_delete_memory_persist_without_touching_conversation(runtime):
    from app import routes_memory
    from app.models import Conversation, MemoryItem
    from app.schemas import MemoryUpdate

    with runtime.db() as db:
        db.add(MemoryItem(id='memory-a', tenant_id='tenant-a', contact_key='synthetic-contact',
                          kind='note', content='fato revisável', approved=False))
        db.commit()
        revision = db.get(Conversation, 'conversation-a').revision
        updated = routes_memory.update_memory('memory-a', payload=MemoryUpdate(approved=True),
                                              db=db, tenant_id='tenant-a', user=runtime.admin)
        assert updated['approved'] is True
        db.expire_all()
        assert db.get(MemoryItem, 'memory-a').approved is True
        assert db.get(Conversation, 'conversation-a').revision == revision
        assert routes_memory.delete_memory('memory-a', db=db, tenant_id='tenant-a',
                                           user=runtime.admin) is None
        db.expire_all()
        assert db.get(MemoryItem, 'memory-a') is None
        assert db.get(Conversation, 'conversation-a').revision == revision


def test_read_decision_reports_selected_provider_and_model(runtime):
    from app import routes_memory
    from app.models import Conversation, ModelRun

    with runtime.db() as db:
        conversation = db.get(Conversation, 'conversation-a')
        conversation.context_state = {'intent': 'pedido', 'pending': ['bairro'],
                                      'decision_action': 'respond', 'segredo': 'não expor'}
        db.add(ModelRun(tenant_id='tenant-a', conversation_id='conversation-a',
                        revision=conversation.revision, context_snapshot_encrypted='synthetic',
                        context_hash='0' * 64, selected_config_id='model-a', status='completed'))
        db.commit()
        payload = routes_memory.read_decision('conversation-a', db=db, tenant_id='tenant-a')
    assert payload['intent'] == 'pedido'
    assert payload['pending'] == ['bairro']
    assert payload['provider'] == 'openai-compatible'
    assert payload['model'] == 'synthetic'
    assert 'segredo' not in payload


def test_business_fact_approval_requires_admin(runtime):
    from types import SimpleNamespace

    from fastapi import HTTPException

    from app import routes_memory
    from app.models import MemoryItem
    from app.schemas import MemoryUpdate

    with runtime.db() as db:
        db.add(MemoryItem(id='memory-business', tenant_id='tenant-a', contact_key='synthetic-contact',
                          kind='business', content='fato comercial', approved=False))
        db.commit()
        with pytest.raises(HTTPException) as failure:
            routes_memory.update_memory('memory-business', payload=MemoryUpdate(approved=True),
                                        db=db, tenant_id='tenant-a',
                                        user=SimpleNamespace(role='agent'))
        assert failure.value.status_code == 403
        db.expire_all()
        assert db.get(MemoryItem, 'memory-business').approved is False
        approved = routes_memory.update_memory('memory-business', payload=MemoryUpdate(approved=True),
                                               db=db, tenant_id='tenant-a',
                                               user=SimpleNamespace(role='tenant_admin'))
        assert approved['approved'] is True
        db.expire_all()
        assert db.get(MemoryItem, 'memory-business').approved is True
