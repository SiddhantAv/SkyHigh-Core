from sqlalchemy import select
from sqlalchemy.orm import Session

from skyhigh.db.models import CheckInSession


class CheckinRepository:
    def get_session_by_id(self, session: Session, session_id: int) -> CheckInSession | None:
        return session.get(CheckInSession, session_id)

    def get_latest_by_passenger_seat(
        self,
        session: Session,
        passenger_id: int,
        seat_id: int,
    ) -> CheckInSession | None:
        stmt = (
            select(CheckInSession)
            .where(
                CheckInSession.passenger_id == passenger_id,
                CheckInSession.seat_id == seat_id,
            )
            .order_by(CheckInSession.id.desc())
            .limit(1)
        )
        return session.execute(stmt).scalar_one_or_none()

    def add_session(self, session: Session, row: CheckInSession) -> CheckInSession:
        session.add(row)
        session.flush()
        return row
