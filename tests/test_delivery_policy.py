from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
from app.policy import advance_status, is_opt_out, sending_denial
from app.llm_client import _provider_error
from app.conversation.humanize import part_delay


def test_part_delay_clamps_and_falls_back_for_outbox_scheduling():
    # Hostile or model-provided values must never produce a negative or runaway delay.
    assert part_delay({'part_delays': [-5, 90]}, 0) == 0.0
    assert part_delay({'part_delays': [-5, 90]}, 1) == 60.0
    # The outbox schedules the next part with ordinal + 1; the final part has no
    # matching plan slot and must fall back to the legacy delay.
    assert part_delay({'part_delays': [1.2, 2.7], 'delay': 3}, 2) == 3.0


def test_opt_out_is_explicit_and_not_a_cancellation_of_a_question():
    assert is_opt_out('Não quero receber mensagens!')
    assert is_opt_out('PARAR')
    assert not is_opt_out('Cancelar orçamento e me informar o endereço')


def test_sending_checks_contact_block_even_with_consent():
    now = datetime.now(timezone.utc)
    instance = SimpleNamespace(is_active=True, sending_enabled=True, status='connected')
    conversation = SimpleNamespace(opted_out=False, consent_status='unknown', status='open', last_incoming_at=now)
    assert sending_denial(instance, conversation, now) is None
    conversation.last_incoming_at = now - timedelta(hours=25)
    assert sending_denial(instance, conversation, now) == 'consent_required'
    conversation.consent_status = 'granted'
    conversation.opted_out = True
    assert sending_denial(instance, conversation, now) == 'contact_blocked'


def test_delivery_never_regresses_from_read_to_sent_or_failure():
    assert advance_status('read', 'sent') == 'read'
    assert advance_status('delivered', 'failed') == 'delivered'
    assert advance_status('unknown', 'delivered') == 'delivered'


@pytest.mark.parametrize('status,body,category,fallback', [
    (429, {'error': {'code': 'insufficient_quota'}}, 'quota', True),
    (429, {}, 'rate_limit', True),
    (402, {}, 'quota', True),
    (401, {}, 'authentication', True),
    (503, {}, 'unavailable', True),
    (400, {'error': {'code': 'content_policy_violation'}}, 'safety', False),
])
def test_provider_errors_are_classified_without_echoing_secret(status, body, category, fallback):
    body.setdefault('error', {})['message'] = 'private-prompt-must-not-escape'
    error = _provider_error(httpx.Response(status, json=body, headers={'retry-after': '12'}))
    assert error.category == category
    assert error.permits_fallback is fallback
    assert error.retry_after == 12
    assert 'private-prompt' not in str(error)
