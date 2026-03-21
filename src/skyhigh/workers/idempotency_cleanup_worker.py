"""Remove stale idempotency rows (TTL from config)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from skyhigh.config import Settings
from skyhigh.repositories.idempotency_repository import IdempotencyRepository


def run_idempotency_cleanup(session: Session, settings: Settings) -> int:
    """Delete idempotency_keys older than idempotency_ttl_hours. Returns rows removed."""
    repo = IdempotencyRepository()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.idempotency_ttl_hours)
    with session.begin():
        return repo.delete_older_than(session, cutoff)
