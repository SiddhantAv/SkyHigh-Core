"""Optional Redis lock for hot seats — PostgreSQL remains authoritative."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis import Redis


@contextmanager
def optional_seat_lock(
    redis: "Redis | None",
    seat_id: int,
    *,
    enabled: bool,
    timeout_sec: float = 5.0,
) -> Iterator[None]:
    if not enabled or redis is None:
        yield
        return
    key = f"lock:seat:{seat_id}"
    with redis.lock(key, timeout=int(timeout_sec), blocking_timeout=int(timeout_sec)):
        yield
