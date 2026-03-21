"""Optional per-seat Redis lock."""

from __future__ import annotations

from unittest.mock import MagicMock

from skyhigh.infrastructure.seat_redis_lock import optional_seat_lock


def test_optional_seat_lock_noop_when_disabled() -> None:
    r = MagicMock()
    with optional_seat_lock(r, 42, enabled=False):
        pass
    r.lock.assert_not_called()


def test_optional_seat_lock_noop_when_redis_none() -> None:
    with optional_seat_lock(None, 42, enabled=True):
        pass


def test_optional_seat_lock_uses_redis_lock_when_enabled() -> None:
    r = MagicMock()
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=True)
    cm.__exit__ = MagicMock(return_value=False)
    r.lock = MagicMock(return_value=cm)
    with optional_seat_lock(r, 99, enabled=True, timeout_sec=2.5):
        pass
    r.lock.assert_called_once_with("lock:seat:99", timeout=2, blocking_timeout=2)
