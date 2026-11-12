from types import SimpleNamespace

from app.routes_memory import _decision_payload, _memory_payload


def test_memory_payload_never_exposes_other_tenant_and_marks_provenance():
    row = SimpleNamespace(id='m1', tenant_id='t1', contact_key='c1', kind='preference',
                          fact_key='preference', content='prefere manhã', approved=True,
                          source='auto_extraction', source_message_id='msg-1',
                          confidence=0.7, created_at=None, last_seen_at=None, expires_at=None)
    payload = _memory_payload(row)
    assert payload['kind'] == 'preference'
    assert payload['source_message_id'] == 'msg-1'
    assert payload['approved'] is True
    assert 'tenant_id' not in payload


def test_decision_payload_only_returns_allowlisted_fields():
    state = {'intent': 'pedido', 'sentiment': 'neutro', 'stage': 'coleta',
             'pending': ['bairro'], 'next_best_action': 'perguntar', 'decision_action': 'respond',
             'segredo': 'não expor'}
    payload = _decision_payload(state)
    assert payload['intent'] == 'pedido'
    assert payload['pending'] == ['bairro']
    assert 'segredo' not in payload
