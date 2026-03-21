"""Batch expiry: HELD seats past held_until → AVAILABLE; invalidate seat-map cache."""

from __future__ import annotations

from datetime import datetime, timezone

from redis import Redis
from sqlalchemy.orm import Session

from skyhigh.config import Settings, get_settings
from skyhigh.infrastructure.cache import invalidate_seat_maps
from skyhigh.repositories.seat_repository import SeatRepository


def run_seat_expiry_job(
    session: Session,
    settings: Settings,
    redis: Redis | None = None,
    *,
    now_utc: datetime | None = None,
    max_rounds: int = 10_000,
) -> int:
    """
    Process expired HELD seats in batches (SKIP LOCKED). Commits each batch.
    Returns total seats updated.
    """
    repo = SeatRepository()
    now = now_utc or datetime.now(timezone.utc)
    total = 0
    for _ in range(max_rounds):
        with session.begin():
            flight_ids = repo.reset_expired_held_seats_batch(
                session,
                now,
                limit=settings.seat_expiry_batch_size,
            )
        n = len(flight_ids)
        if n == 0:
            break
        total += n
        invalidate_seat_maps(redis, flight_ids)
    return total


def expire_held_seats_once(
    session: Session,
    now_utc: datetime | None = None,
    redis: Redis | None = None,
) -> int:
    """Run full batched expiry (tests / simple callers)."""
    return run_seat_expiry_job(session, get_settings(), redis=redis, now_utc=now_utc)
