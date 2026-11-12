from datetime import datetime, timedelta, timezone

from app.conversation.memory import memory_context, record_facts
from app.models import MemoryItem


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
