from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.conversation.memory import memory_context, record_facts
from app.models import Agent, Conversation, MemoryItem, Message


def test_deterministic_fact_outranks_later_semantic_writes(runtime):
    now = datetime.now(timezone.utc)
    with runtime.db() as db:
        record_facts(db, tenant_id='tenant-a', contact_key='synthetic-contact', facts={'city': 'Campinas'},
                     message_id='msg-1', captured_at=now, source='auto_extraction', confidence=0.7)
        db.commit()
        record_facts(db, tenant_id='tenant-a', contact_key='synthetic-contact', facts={'city': 'Santos'},
                     message_id='msg-2', captured_at=now + timedelta(minutes=1), source='deterministic')
        db.commit()
        record_facts(db, tenant_id='tenant-a', contact_key='synthetic-contact', facts={'city': 'Recife'},
                     message_id='msg-3', captured_at=now + timedelta(minutes=2), source='auto_extraction')
        db.commit()
        row = (db.query(MemoryItem)
               .filter_by(tenant_id='tenant-a', contact_key='synthetic-contact', fact_key='city').one())
    assert row.content == 'Santos'
    assert row.source == 'deterministic'
    assert row.source_message_id == 'msg-2'
    assert row.approved


def test_memory_context_only_returns_approved_unexpired_provenanced_tenant_rows(runtime):
    now = datetime.now(timezone.utc)
    common = dict(tenant_id='tenant-a', contact_key='synthetic-contact', source='auto_extraction')
    with runtime.db() as db:
        db.add_all([
            MemoryItem(**common, content='cidade Campinas', approved=True, kind='episode',
                       fact_key='city', source_message_id='msg-ok', last_seen_at=now),
            MemoryItem(tenant_id='tenant-b', contact_key='synthetic-contact', source='auto_extraction',
                       content='outro tenant', approved=True, kind='episode', source_message_id='msg-other'),
            MemoryItem(**common, content='não aprovado', approved=False, kind='business',
                       source_message_id='msg-unapproved'),
            MemoryItem(**common, content='expirado', approved=True, kind='episode',
                       source_message_id='msg-expired', expires_at=now - timedelta(days=1)),
            MemoryItem(**common, content='sem proveniência', approved=True, kind='episode',
                       source_message_id=None),
            MemoryItem(**common, content='proveniência vazia', approved=True, kind='episode',
                       source_message_id=''),
        ])
        db.commit()
        block = memory_context(db, tenant_id='tenant-a', contact_key='synthetic-contact', now=now)
    assert 'cidade Campinas' in block
    assert 'outro tenant' not in block
    assert 'não aprovado' not in block
    assert 'expirado' not in block
    assert 'sem proveniência' not in block
    assert 'proveniência vazia' not in block


def test_record_facts_without_message_id_writes_nothing(runtime):
    now = datetime.now(timezone.utc)
    with runtime.db() as db:
        record_facts(db, tenant_id='tenant-a', contact_key='synthetic-contact',
                     facts={'city': 'Campinas'}, message_id=None, captured_at=now)
        record_facts(db, tenant_id='tenant-a', contact_key='synthetic-contact',
                     facts={'city': 'Campinas'}, message_id='', captured_at=now)
        db.commit()
        assert db.query(MemoryItem).count() == 0


def test_summary_cursor_includes_later_messages_with_the_same_timestamp(runtime, monkeypatch):
    stamp = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)
    with runtime.db() as db:
        conversation = db.get(Conversation, 'conversation-a')
        conversation.context_state = {'summary_cursor': stamp.isoformat(), 'summary_cursor_id': 'message-0003'}
        agent = db.get(Agent, 'agent-a')
        agent.conversation_profile = {'enabled': True, 'memory_enabled': True}
        for number in range(1, 13):
            db.add(Message(id=f'message-{number:04d}', tenant_id='tenant-a',
                           conversation_id='conversation-a', direction='incoming',
                           content=f'synthetic message {number}', created_at=stamp))
        db.commit()

    prompts = []
    monkeypatch.setattr(runtime.tasks, 'complete', lambda *args, **kwargs: prompts.append(args[5][0]['content']) or 'resumo sintético')
    result = runtime.tasks.summarize_conversation.run('tenant-a', 'conversation-a', 1)

    assert result == 'summarized'
    assert len(prompts) == 1
    assert 'synthetic message 3' not in prompts[0]
    assert 'synthetic message 4' in prompts[0]
    with runtime.db() as db:
        state = db.get(Conversation, 'conversation-a').context_state
    assert state['summary_cursor_id'] == 'message-0012'
    assert state['summary_cursor'] == stamp.isoformat()


def test_delete_business_memory_requires_admin_and_scopes_tenant(runtime, monkeypatch):
    from fastapi.testclient import TestClient
    from app.database import get_db
    from app.dependencies import get_current_user
    from app.main import app

    with runtime.db() as db:
        db.add_all([
            MemoryItem(id='business-memory-a', tenant_id='tenant-a', contact_key='synthetic-contact',
                       kind='business', fact_key='objective', content='fato comercial A', approved=False,
                       source='operator'),
            MemoryItem(id='business-memory-b', tenant_id='tenant-b', contact_key='synthetic-contact',
                       kind='business', fact_key='objective', content='fato comercial B', approved=False,
                       source='operator'),
        ])
        db.commit()

    def db_dependency():
        with runtime.db() as db:
            yield db

    current = {'user': SimpleNamespace(role='operator', tenant_id='tenant-a', id='synthetic-operator')}
    monkeypatch.setitem(app.dependency_overrides, get_db, db_dependency)
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: current['user'])

    with TestClient(app) as client:
        denied = client.delete('/api/memory/business-memory-a')
        cross_tenant = client.delete('/api/memory/business-memory-b')
        current['user'] = SimpleNamespace(role='tenant_admin', tenant_id='tenant-a', id='synthetic-admin')
        allowed = client.delete('/api/memory/business-memory-a')

    assert denied.status_code == 403
    assert cross_tenant.status_code == 404
    assert allowed.status_code == 204
    with runtime.db() as db:
        assert db.get(MemoryItem, 'business-memory-a') is None
        assert db.get(MemoryItem, 'business-memory-b') is not None


def test_summary_cursor_keeps_legacy_timestamp_compatibility(runtime, monkeypatch):
    stamp = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)
    with runtime.db() as db:
        conversation = db.get(Conversation, 'conversation-a')
        conversation.context_state = {'summary_cursor': stamp.isoformat()}
        agent = db.get(Agent, 'agent-a')
        agent.conversation_profile = {'enabled': True, 'memory_enabled': True}
        db.add_all([
            Message(id=f'legacy-{number:04d}', tenant_id='tenant-a', conversation_id='conversation-a',
                    direction='incoming', content=f'legacy synthetic {number}',
                    created_at=stamp + timedelta(minutes=number))
            for number in range(0, 9)
        ])
        db.commit()

    prompts = []
    monkeypatch.setattr(runtime.tasks, 'complete', lambda *args, **kwargs: prompts.append(args[5][0]['content']) or 'resumo legado')
    assert runtime.tasks.summarize_conversation.run('tenant-a', 'conversation-a', 1) == 'summarized'
    assert 'legacy synthetic 0' in prompts[0]
    assert 'legacy synthetic 1' in prompts[0]
