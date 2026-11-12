"""Delivery pacing and anti-repetition. No change to message content."""
from hashlib import sha256
import re

from app.conversation.behavior import normalize

WAIT_TOKENS = frozenset({'ok', 'okay', 'beleza', 'blz', 'valeu', 'vlw', 'obrigado',
                         'obrigada', '👍', '🙏'})


def _jitter(seed, low=0.0, high=1.2):
    value = int.from_bytes(sha256(seed.encode()).digest()[:8], 'big')
    return low + (value / 2 ** 64) * (high - low)


def delivery_plan(parts, message_id):
    plan = []
    for ordinal, part in enumerate(parts):
        delay = min(6.0, max(1.0, 1.0 + 0.02 * len(part) + _jitter(f'{message_id}:{ordinal}')))
        if ordinal:
            delay = max(1.5, delay)
        plan.append(round(delay, 2))
    return plan


def part_delay(delivery_config, ordinal):
    plan = (delivery_config or {}).get('part_delays')
    if isinstance(plan, list) and ordinal < len(plan):
        try:
            return max(0.0, min(60.0, float(plan[ordinal])))
        except (TypeError, ValueError):
            pass
    return float((delivery_config or {}).get('delay', 1))


def should_wait(text, pending, last_assistant):
    if pending:
        return False
    if '?' in str(last_assistant or ''):
        return False
    value = str(text or '').strip()
    return value in WAIT_TOKENS or normalize(value).strip() in WAIT_TOKENS


def opening(text):
    return str(text or '').strip()[:40]


def _greeting(text):
    """First phrase of an opening, used to detect repeated greetings."""
    return re.split(r'[.!?…]', opening(text), maxsplit=1)[0].strip().casefold()


def remember_opening(state, answer):
    updated = dict(state or {})
    updated['recent_openings'] = (list(updated.get('recent_openings') or [])[-4:] + [opening(answer)])[-5:]
    return updated


def repeated_opening(state, answer):
    key = _greeting(answer)
    return bool(key) and key in {_greeting(item) for item in (state or {}).get('recent_openings', [])}
