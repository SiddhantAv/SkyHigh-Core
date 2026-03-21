from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from skyhigh.db.models import IdempotencyKey


class IdempotencyRepository:
    def get_by_key(self, session: Session, key: str) -> IdempotencyKey | None:
        return session.execute(
            select(IdempotencyKey).where(IdempotencyKey.key == key)
        ).scalar_one_or_none()

    def get_by_key_for_update(self, session: Session, key: str) -> IdempotencyKey | None:
        return session.execute(
            select(IdempotencyKey).where(IdempotencyKey.key == key).with_for_update()
        ).scalar_one_or_none()

    def create_key(self, session: Session, key: str) -> IdempotencyKey:
        row = IdempotencyKey(key=key, response_data=None)
        session.add(row)
        session.flush()
        return row

    def get_or_create_for_update(self, session: Session, key: str) -> IdempotencyKey:
        """Serialize concurrent idempotent holds on the same key (FOR UPDATE + nested insert)."""
        row = self.get_by_key_for_update(session, key)
        if row is not None:
            return row
        with session.begin_nested():
            row = IdempotencyKey(key=key, response_data=None)
            session.add(row)
            try:
                session.flush()
            except IntegrityError:
                pass
        row = self.get_by_key_for_update(session, key)
        if row is None:
            raise RuntimeError("idempotency key missing after concurrent insert")
        return row

    def delete_older_than(self, session: Session, cutoff_utc: datetime) -> int:
        """Remove idempotency rows older than cutoff (UTC). Returns deleted count."""
        result = session.execute(delete(IdempotencyKey).where(IdempotencyKey.created_at < cutoff_utc))
        return int(result.rowcount or 0)
