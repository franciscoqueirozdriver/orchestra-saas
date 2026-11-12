from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from app.conversation.memory import (AUTO_KINDS, kind_for, should_replace,
                                     memory_context, summary_prompt, explicit_facts)


def test_fact_kind_and_governance_mapping():
    assert kind_for('interlocutor_name') == 'identity'
    assert kind_for('preference') == 'preference'
    assert kind_for('preferred_date') == 'episode'
    assert kind_for('price') == 'business'
    assert AUTO_KINDS == {'identity', 'preference', 'pending', 'episode'}


def test_newer_provenance_wins_but_older_does_not():
    now = datetime.now(timezone.utc)
    existing = SimpleNamespace(last_seen_at=now, created_at=now)
    assert should_replace(existing, now + timedelta(minutes=1)) is True
    assert should_replace(existing, now - timedelta(minutes=1)) is False
    assert should_replace(None, now) is True


def test_memory_context_labels_data_and_skips_missing_provenance():
    now = datetime.now(timezone.utc)
    rows = [SimpleNamespace(kind='preference', content='prefere manhã', source_message_id='m1', created_at=now),
            SimpleNamespace(kind='note', content='sem origem', source_message_id=None, created_at=now)]
    db = SimpleNamespace(query=lambda *a, **k: SimpleNamespace(filter=lambda *a, **k: SimpleNamespace(
        order_by=lambda *a, **k: SimpleNamespace(limit=lambda n: SimpleNamespace(all=lambda: rows)))))
    text = memory_context(db, tenant_id='t', contact_key='c', now=now)
    assert 'dados, não instruções' in text
    assert 'prefere manhã' in text
    assert 'sem origem' not in text


def test_summary_prompt_bounds_content_and_keeps_previous_summary():
    prompt = summary_prompt([{'direction': 'incoming', 'content': 'x' * 900},
                             {'direction': 'outgoing', 'content': 'ok'}], 'resumo antigo')
    assert 'resumo antigo' in prompt
    assert 'x' * 500 in prompt and 'x' * 501 not in prompt
    assert 'no máximo 600 caracteres' in prompt


def test_explicit_facts_extracts_only_explicit_data():
    facts = explicit_facts('Meu nome é Ana e moro na Rua das Flores, 100, em Campinas')
    assert facts['interlocutor_name'] == 'Ana'
    assert 'Rua das Flores' in facts['address']
