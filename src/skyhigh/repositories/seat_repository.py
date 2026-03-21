from datetime import datetime
from typing import Any

from sqlalchemy import or_, select, text, update
from sqlalchemy.orm import Session

from skyhigh.db.models import Seat
from skyhigh.db.models.enums import SeatStatus


class SeatRepository:
    """Data access for seats — row locks live here for concurrency-safe updates."""

    def get_seat_by_id(self, session: Session, seat_id: int) -> Seat | None:
        return session.get(Seat, seat_id)

    def get_seat_for_update(self, session: Session, seat_id: int) -> Seat | None:
        stmt = select(Seat).where(Seat.id == seat_id).with_for_update()
        return session.execute(stmt).scalar_one_or_none()

    def get_seat_map_by_flight(self, session: Session, flight_id: int) -> list[dict[str, Any]]:
        stmt = (
            select(Seat.id, Seat.seat_number, Seat.status)
            .where(Seat.flight_id == flight_id)
            .order_by(Seat.seat_number)
        )
        rows = session.execute(stmt).all()
        return [
            {
                "seat_id": int(r[0]),
                "seat_number": str(r[1]),
                "status": r[2].value,
            }
            for r in rows
        ]

    def update_seat(self, session: Session, seat: Seat) -> None:
        session.add(seat)

    def reset_expired_seat_if_needed(
        self,
        session: Session,
        seat: Seat,
        now_utc: datetime,
    ) -> bool:
        """
        Lazy expiry: HELD + held_until in the past → AVAILABLE.
        Returns True if the seat was reset.
        """
        if seat.status != SeatStatus.HELD:
            return False
        if seat.held_until is not None and seat.held_until >= now_utc:
            return False
        seat.status = SeatStatus.AVAILABLE
        seat.held_by = None
        seat.held_until = None
        session.add(seat)
        return True

    def reset_expired_held_seats_for_flight(
        self,
        session: Session,
        flight_id: int,
        now_utc: datetime,
    ) -> int:
        """Seat-map read path: expired HELD → AVAILABLE for one flight only."""
        result = session.execute(
            update(Seat)
            .where(
                Seat.flight_id == flight_id,
                Seat.status == SeatStatus.HELD,
                or_(Seat.held_until.is_(None), Seat.held_until < now_utc),
            )
            .values(
                status=SeatStatus.AVAILABLE,
                held_by=None,
                held_until=None,
            )
        )
        return int(result.rowcount or 0)

    def reset_expired_held_seats(self, session: Session, now_utc: datetime) -> int:
        """Bulk worker: clear expired HELD seats."""
        result = session.execute(
            update(Seat)
            .where(
                Seat.status == SeatStatus.HELD,
                or_(Seat.held_until.is_(None), Seat.held_until < now_utc),
            )
            .values(
                status=SeatStatus.AVAILABLE,
                held_by=None,
                held_until=None,
            )
        )
        return int(result.rowcount or 0)

    def reset_expired_held_seats_batch(
        self,
        session: Session,
        now_utc: datetime,
        *,
        limit: int = 500,
    ) -> list[int]:
        """
        PostgreSQL: update up to `limit` expired HELD rows using SKIP LOCKED.
        Returns flight_id per updated row (may contain duplicates).
        """
        result = session.execute(
            text(
                """
                WITH picked AS (
                    SELECT id, flight_id FROM seats
                    WHERE status = 'HELD'
                      AND (held_until IS NULL OR held_until < :now)
                    ORDER BY id
                    LIMIT :lim
                    FOR UPDATE SKIP LOCKED
                )
                UPDATE seats AS s
                SET status = CAST('AVAILABLE' AS seat_status), held_by = NULL, held_until = NULL
                FROM picked
                WHERE s.id = picked.id
                RETURNING picked.flight_id
                """
            ),
            {"now": now_utc, "lim": limit},
        )
        return [int(row[0]) for row in result]
