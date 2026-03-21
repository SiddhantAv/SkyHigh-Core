"""SeatRepository methods that run on SQLite (integration)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from skyhigh.db.models import Flight, Passenger, Seat
from skyhigh.db.models.enums import SeatStatus
from skyhigh.repositories.seat_repository import SeatRepository


def test_get_seat_map_by_flight_orders_by_seat_number(db_session) -> None:
    fl = Flight(flight_number="R1", departure_time=datetime.now(timezone.utc))
    db_session.add(fl)
    db_session.flush()
    for num in ("2B", "1A"):
        db_session.add(
            Seat(
                flight_id=fl.id,
                seat_number=num,
                status=SeatStatus.AVAILABLE,
                held_by=None,
                held_until=None,
            )
        )
    db_session.commit()
    repo = SeatRepository()
    rows = repo.get_seat_map_by_flight(db_session, fl.id)
    assert [r["seat_number"] for r in rows] == ["1A", "2B"]


def test_reset_expired_seat_if_needed_false_when_not_held(db_session) -> None:
    fl = Flight(flight_number="R2", departure_time=datetime.now(timezone.utc))
    db_session.add(fl)
    db_session.flush()
    st = Seat(
        flight_id=fl.id,
        seat_number="9Z",
        status=SeatStatus.AVAILABLE,
        held_by=None,
        held_until=None,
    )
    db_session.add(st)
    db_session.commit()
    repo = SeatRepository()
    now = datetime.now(timezone.utc)
    assert repo.reset_expired_seat_if_needed(db_session, st, now) is False


def test_reset_expired_seat_if_needed_false_when_hold_still_valid(db_session) -> None:
    fl = Flight(flight_number="R3", departure_time=datetime.now(timezone.utc))
    db_session.add(fl)
    db_session.flush()
    p = Passenger(name="p")
    db_session.add(p)
    db_session.flush()
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    st = Seat(
        flight_id=fl.id,
        seat_number="9Y",
        status=SeatStatus.HELD,
        held_by=p.id,
        held_until=future,
    )
    db_session.add(st)
    db_session.commit()
    repo = SeatRepository()
    assert repo.reset_expired_seat_if_needed(db_session, st, datetime.now(timezone.utc)) is False


def test_reset_expired_seat_if_needed_clears_expired_hold(db_session) -> None:
    fl = Flight(flight_number="R4", departure_time=datetime.now(timezone.utc))
    db_session.add(fl)
    db_session.flush()
    p = Passenger(name="q")
    db_session.add(p)
    db_session.flush()
    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    st = Seat(
        flight_id=fl.id,
        seat_number="9X",
        status=SeatStatus.HELD,
        held_by=p.id,
        held_until=past,
    )
    db_session.add(st)
    db_session.commit()
    repo = SeatRepository()
    assert repo.reset_expired_seat_if_needed(db_session, st, datetime.now(timezone.utc)) is True
    db_session.flush()
    db_session.refresh(st)
    assert st.status == SeatStatus.AVAILABLE
    assert st.held_by is None
    assert st.held_until is None


def test_reset_expired_held_seats_for_flight(db_session) -> None:
    fl = Flight(flight_number="R5", departure_time=datetime.now(timezone.utc))
    db_session.add(fl)
    db_session.flush()
    p = Passenger(name="r")
    db_session.add(p)
    db_session.flush()
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.add(
        Seat(
            flight_id=fl.id,
            seat_number="1A",
            status=SeatStatus.HELD,
            held_by=p.id,
            held_until=past,
        )
    )
    db_session.commit()
    repo = SeatRepository()
    with db_session.begin():
        n = repo.reset_expired_held_seats_for_flight(db_session, fl.id, datetime.now(timezone.utc))
    assert n == 1


def test_reset_expired_held_seats_bulk(db_session) -> None:
    fl = Flight(flight_number="R6", departure_time=datetime.now(timezone.utc))
    db_session.add(fl)
    db_session.flush()
    p = Passenger(name="s")
    db_session.add(p)
    db_session.flush()
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    for sn in ("1A", "1B"):
        db_session.add(
            Seat(
                flight_id=fl.id,
                seat_number=sn,
                status=SeatStatus.HELD,
                held_by=p.id,
                held_until=past,
            )
        )
    db_session.commit()
    repo = SeatRepository()
    with db_session.begin():
        n = repo.reset_expired_held_seats(db_session, datetime.now(timezone.utc))
    assert n == 2
