import json
from app.conversation.decision import clean_visit, parse_decision_envelope, state_patch, contract_instructions


def _envelope(**overrides):
    decision = {
        'intent': 'pedido', 'sentiment': 'neutro', 'stage': 'coletando',
        'action': 'respond', 'facts': {'interlocutor_name': 'Ana', 'inventado': 'x'},
        'pending': ['confirmar bairro'], 'next_best_action': 'responder',
    }
    decision.update(overrides)
    return json.dumps({'reply': 'Claro, Ana. Qual o bairro?', 'decision': decision})


def test_parses_valid_envelope_and_drops_unknown_fact_keys():
    envelope = parse_decision_envelope(_envelope())
    assert envelope['reply'] == 'Claro, Ana. Qual o bairro?'
    assert envelope['decision']['facts'] == {'interlocutor_name': 'Ana'}
    assert envelope['decision']['pending'] == ['confirmar bairro']
    assert envelope['decision']['action'] == 'respond'


def test_rejects_invalid_or_out_of_allowlist_output():
    assert parse_decision_envelope('texto livre') is None
    assert parse_decision_envelope(json.dumps({'reply': '', 'decision': {}})) is None
    assert parse_decision_envelope(_envelope(action='delete')) is None
    assert parse_decision_envelope(_envelope(intent='qualquer')) is None
    assert parse_decision_envelope(json.dumps({'reply': 'ok', 'decision': {'intent': 'pedido'}})) is None


def test_accepts_fenced_json_and_limits_pending():
    fenced = '```json\n' + _envelope(pending=['a'] * 20) + '\n```'
    envelope = parse_decision_envelope(fenced)
    assert len(envelope['decision']['pending']) == 10


def test_state_patch_carries_only_allowlisted_fields():
    envelope = parse_decision_envelope(_envelope())
    patch = state_patch(envelope['decision'])
    assert patch['intent'] == 'pedido'
    assert patch['pending'] == ['confirmar bairro']
    assert patch['decision_action'] == 'respond'
    assert 'facts' not in patch


def test_visit_block_is_optional_but_validated_when_present():
    assert clean_visit(None) is None
    assert clean_visit({'channel_confirmation': 'nope'}) is None
    good = clean_visit({'channel_confirmation': 'use_current', 'receiver_confirmation': 'customer',
                        'receiver_name': None, 'next_required_field': 'city'})
    assert good['receiver_confirmation'] == 'customer'


def test_rejects_unhashable_or_non_list_decision_fields():
    assert parse_decision_envelope(_envelope(intent=['pedido'])) is None
    assert parse_decision_envelope(_envelope(intent={'valor': 'pedido'})) is None
    assert parse_decision_envelope(_envelope(sentiment=['neutro'])) is None
    assert parse_decision_envelope(_envelope(action={'valor': 'respond'})) is None
    assert parse_decision_envelope(_envelope(pending=3)) is None
    assert parse_decision_envelope(_envelope(pending=True)) is None
    assert parse_decision_envelope(_envelope(pending='confirmar bairro')) is None


def test_rejects_non_dict_json_values():
    for raw in ('[]', 'null', '"str"', '42', 'true'):
        assert parse_decision_envelope(raw) is None


def test_clean_visit_rejects_non_string_fields():
    base = {'channel_confirmation': 'use_current', 'receiver_confirmation': 'customer',
            'next_required_field': 'city'}
    assert clean_visit({**base, 'channel_confirmation': ['use_current']}) is None
    assert clean_visit({**base, 'receiver_confirmation': {'valor': 'customer'}}) is None
    assert clean_visit({**base, 'next_required_field': ['city']}) is None


def test_contract_mentions_visit_only_when_needed():
    assert 'visit' in contract_instructions(True)
    assert 'visit' not in contract_instructions(False)
    assert 'conversation.v1' in contract_instructions(False)
