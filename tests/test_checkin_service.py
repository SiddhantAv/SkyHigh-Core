"""Check-in business rules (SQLite); each service call uses a fresh Session to avoid nested transaction issues."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from skyhigh.config import Settings
from skyhigh.db.base import Base
from skyhigh.db.models import CheckInSession, Flight, Passenger, Seat
from skyhigh.db.models.enums import CheckInStatus, PaymentStatus, SeatStatus
from skyhigh.db.session import SessionLocal, engine
from skyhigh.exceptions import CheckInSessionNotFoundError, InvalidPaymentStateError, SeatNotReadyForCheckInError
from skyhigh.repositories.checkin_repository import CheckinRepository
from skyhigh.repositories.seat_repository import SeatRepository
from skyhigh.services.checkin_service import CheckinService


@pytest.fixture(autouse=True)
def _reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def checkin_svc() -> CheckinService:
    return CheckinService(CheckinRepository(), SeatRepository(), Settings())


def _seed_confirmed_seat(s: Session) -> tuple[int, int]:
    fl = Flight(flight_number="X1", departure_time=datetime.now(timezone.utc))
    s.add(fl)
    s.flush()
    p = Passenger(name="Alice")
    s.add(p)
    s.flush()
    st = Seat(
        flight_id=fl.id,
        seat_number="2B",
        status=SeatStatus.CONFIRMED,
        held_by=p.id,
        held_until=None,
    )
    s.add(st)
    s.commit()
    return p.id, st.id


def test_start_checkin_within_limit_then_complete(checkin_svc: CheckinService) -> None:
    s0 = SessionLocal()
    try:
        pid, sid = _seed_confirmed_seat(s0)
    finally:
        s0.close()

    s1 = SessionLocal()
    try:
        out = checkin_svc.start_checkin(s1, pid, sid, 18.0)
        assert out["status"] == CheckInStatus.IN_PROGRESS.value
    finally:
        s1.close()

    s2 = SessionLocal()
    try:
        done = checkin_svc.complete_checkin(s2, pid, sid)
        assert done["status"] == CheckInStatus.COMPLETED.value
    finally:
        s2.close()


def test_start_checkin_overweight_then_pay(checkin_svc: CheckinService) -> None:
    s0 = SessionLocal()
    try:
        pid, sid = _seed_confirmed_seat(s0)
    finally:
        s0.close()

    s1 = SessionLocal()
    try:
        out = checkin_svc.start_checkin(s1, pid, sid, 30.0)
        assert out["status"] == CheckInStatus.WAITING_FOR_PAYMENT.value
        cid = out["data"]["checkin_session_id"]
    finally:
        s1.close()

    s2 = SessionLocal()
    try:
        paid = checkin_svc.complete_payment(s2, cid)
        assert paid["status"] == CheckInStatus.COMPLETED.value
    finally:
        s2.close()


def test_complete_payment_not_found(checkin_svc: CheckinService) -> None:
    s = SessionLocal()
    try:
        with pytest.raises(CheckInSessionNotFoundError):
            checkin_svc.complete_payment(s, 999_999)
    finally:
        s.close()


def test_complete_payment_wrong_state(checkin_svc: CheckinService) -> None:
    s0 = SessionLocal()
    try:
        pid, sid = _seed_confirmed_seat(s0)
    finally:
        s0.close()

    s1 = SessionLocal()
    try:
        checkin_svc.start_checkin(s1, pid, sid, 10.0)
    finally:
        s1.close()

    s2 = SessionLocal()
    try:
        row = s2.execute(
            select(CheckInSession).order_by(CheckInSession.id.desc()).limit(1)
        ).scalar_one_or_none()
        assert row is not None
        cid = row.id
        s2.commit()
    finally:
        s2.close()

    s3 = SessionLocal()
    try:
        with pytest.raises(InvalidPaymentStateError):
            checkin_svc.complete_payment(s3, cid)
    finally:
        s3.close()


def test_start_checkin_seat_not_confirmed(checkin_svc: CheckinService) -> None:
    s = SessionLocal()
    try:
        fl = Flight(flight_number="Y1", departure_time=datetime.now(timezone.utc))
        s.add(fl)
        s.flush()
        p = Passenger(name="Bob")
        s.add(p)
        s.flush()
        st = Seat(
            flight_id=fl.id,
            seat_number="3C",
            status=SeatStatus.AVAILABLE,
            held_by=None,
            held_until=None,
        )
        s.add(st)
        s.commit()
        with pytest.raises(SeatNotReadyForCheckInError):
            checkin_svc.start_checkin(s, p.id, st.id, 10.0)
    finally:
        s.close()
