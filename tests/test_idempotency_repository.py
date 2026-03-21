"""IdempotencyRepository CRUD and get_or_create."""

from __future__ import annotations

from skyhigh.db.models import IdempotencyKey
from skyhigh.repositories.idempotency_repository import IdempotencyRepository


def test_get_by_key_missing_returns_none(db_session) -> None:
    repo = IdempotencyRepository()
    assert repo.get_by_key(db_session, "no-such") is None


def test_create_key_and_get_by_key(db_session) -> None:
    repo = IdempotencyRepository()
    with db_session.begin():
        row = repo.create_key(db_session, "idem-1")
    assert row.id is not None
    found = repo.get_by_key(db_session, "idem-1")
    assert found is not None
    assert found.key == "idem-1"


def test_get_or_create_for_update_returns_existing(db_session) -> None:
    repo = IdempotencyRepository()
    with db_session.begin():
        repo.create_key(db_session, "shared-key")
    with db_session.begin():
        a = repo.get_or_create_for_update(db_session, "shared-key")
        b = repo.get_or_create_for_update(db_session, "shared-key")
    assert a.id == b.id


def test_get_or_create_for_update_inserts_new(db_session) -> None:
    repo = IdempotencyRepository()
    with db_session.begin():
        row = repo.get_or_create_for_update(db_session, "brand-new")
    assert row.key == "brand-new"


def test_delete_older_than(db_session) -> None:
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import update

    repo = IdempotencyRepository()
    with db_session.begin():
        repo.create_key(db_session, "old-row")
    row = repo.get_by_key(db_session, "old-row")
    assert row is not None
    old = datetime.now(timezone.utc) - timedelta(days=10)
    db_session.execute(
        update(IdempotencyKey).where(IdempotencyKey.id == row.id).values(created_at=old)
    )
    db_session.commit()
    with db_session.begin():
        n = repo.delete_older_than(db_session, datetime.now(timezone.utc) - timedelta(days=1))
    assert n >= 1
