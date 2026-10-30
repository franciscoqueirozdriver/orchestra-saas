from datetime import datetime, timedelta, timezone

from app.tasks import _window_remaining


def test_window_waits_until_last_fragment_is_quiet():
    now = datetime.now(timezone.utc)
    assert _window_remaining(now - timedelta(seconds=1), now, 3) == 2
    assert _window_remaining(now - timedelta(seconds=4), now, 3) == 0


def test_zero_window_is_immediate():
    now = datetime.now(timezone.utc)
    assert _window_remaining(now, now, 0) == 0
