"""Extra SeatService paths (cache hit, hold phrases, passenger rate limit, confirm rules)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

import skyhigh.services.seat_service as seat_service_mod
from skyhigh.config import get_settings
from skyhigh.db.models import Flight, Passenger, Seat
from skyhigh.db.models.enums import SeatStatus
from skyhigh.db.session import SessionLocal
from skyhigh.exceptions import PassengerHoldRateLimitedError, SeatAlreadyHeldError, SeatHoldExpiredError
from skyhigh.repositories.idempotency_repository import IdempotencyRepository
from skyhigh.repositories.seat_repository import SeatRepository
from skyhigh.services.seat_service import SeatService


def test_hold_duration_phrase_variants() -> None:
    assert seat_service_mod._hold_duration_phrase(0) == "a short time"
    assert seat_service_mod._hold_duration_phrase(3600) == "1 hour"
    assert seat_service_mod._hold_duration_phrase(7200) == "2 hours"
    assert seat_service_mod._hold_duration_phrase(60) == "1 minute"
    assert seat_service_mod._hold_duration_phrase(120) == "2 minutes"
    assert seat_service_mod._hold_duration_phrase(45) == "45 seconds"


@patch("skyhigh.services.seat_service.cache_get_seat_map")
@patch("skyhigh.services.seat_service.cache_set_seat_map")
def test_get_seat_map_returns_cached_rows(
    _mock_set: MagicMock,
    mock_get: MagicMock,
    db_session,
    fake_redis: MagicMock,
) -> None:
    fl = Flight(flight_number="C1", departure_time=datetime.now(timezone.utc))
    db_session.add(fl)
    db_session.commit()
    cached = [{"seat_id": 1, "seat_number": "1A", "status": "AVAILABLE"}]
    mock_get.return_value = cached
    settings = get_settings().model_copy(update={"use_redis_seat_lock": False})
    svc = SeatService(SeatRepository(), IdempotencyRepository(), settings, redis=fake_redis)
    out = svc.get_seat_map(db_session, fl.id)
    assert out == cached
    mock_get.assert_called_once_with(fake_redis, fl.id)


def test_hold_seat_passenger_rate_limit_triggers(fake_redis: MagicMock, db_session) -> None:
    fl = Flight(flight_number="C2", departure_time=datetime.now(timezone.utc))
    db_session.add(fl)
    db_session.flush()
    p = Passenger(name="rl")
    db_session.add(p)
    db_session.flush()
    st = Seat(
        flight_id=fl.id,
        seat_number="1A",
        status=SeatStatus.AVAILABLE,
        held_by=None,
        held_until=None,
    )
    db_session.add(st)
    db_session.commit()
    fake_redis.incr = MagicMock(return_value=99)
    fake_redis.expire = MagicMock()
    settings = get_settings().model_copy(
        update={
            "use_redis_seat_lock": False,
            "passenger_hold_rate_limit_enabled": True,
            "passenger_hold_rate_per_minute": 5,
        }
    )
    svc = SeatService(SeatRepository(), IdempotencyRepository(), settings, redis=fake_redis)
    with pytest.raises(PassengerHoldRateLimitedError):
        svc.hold_seat(db_session, p.id, st.id, "idem-rl-1")


@patch("skyhigh.services.seat_service.log")
def test_hold_seat_passenger_rate_limit_fails_open_on_redis_error(
    mock_log: MagicMock,
    fake_redis: MagicMock,
    db_session,
) -> None:
    fl = Flight(flight_number="C3", departure_time=datetime.now(timezone.utc))
    db_session.add(fl)
    db_session.flush()
    p = Passenger(name="fo")
    db_session.add(p)
    db_session.flush()
    st = Seat(
        flight_id=fl.id,
        seat_number="2A",
        status=SeatStatus.AVAILABLE,
        held_by=None,
        held_until=None,
    )
    db_session.add(st)
    db_session.commit()
    fake_redis.incr = MagicMock(side_effect=OSError("boom"))
    settings = get_settings().model_copy(
        update={
            "use_redis_seat_lock": False,
            "passenger_hold_rate_limit_enabled": True,
            "passenger_hold_rate_per_minute": 1,
        }
    )
    svc = SeatService(SeatRepository(), IdempotencyRepository(), settings, redis=fake_redis)
    out = svc.hold_seat(db_session, p.id, st.id, "idem-fo-1")
    assert out["status"] == "HELD"
    mock_log.warning.assert_called_once()


def test_confirm_seat_expired_hold_same_passenger_raises_hold_expired(db_session, fake_redis: MagicMock) -> None:
    fl = Flight(flight_number="C4", departure_time=datetime.now(timezone.utc))
    db_session.add(fl)
    db_session.flush()
    p = Passenger(name="exp")
    db_session.add(p)
    db_session.flush()
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    st = Seat(
        flight_id=fl.id,
        seat_number="3A",
        status=SeatStatus.HELD,
        held_by=p.id,
        held_until=past,
    )
    db_session.add(st)
    db_session.commit()
    settings = get_settings().model_copy(update={"use_redis_seat_lock": False})
    svc = SeatService(SeatRepository(), IdempotencyRepository(), settings, redis=fake_redis)
    with pytest.raises(SeatHoldExpiredError):
        svc.confirm_seat(db_session, p.id, st.id, "idem-exp")


def test_confirm_seat_expired_hold_other_passenger_resets_and_conflict(db_session, fake_redis: MagicMock) -> None:
    fl = Flight(flight_number="C5", departure_time=datetime.now(timezone.utc))
    db_session.add(fl)
    db_session.flush()
    p1 = Passenger(name="owner")
    p2 = Passenger(name="other")
    db_session.add(p1)
    db_session.add(p2)
    db_session.flush()
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    st = Seat(
        flight_id=fl.id,
        seat_number="4A",
        status=SeatStatus.HELD,
        held_by=p1.id,
        held_until=past,
    )
    db_session.add(st)
    db_session.commit()
    settings = get_settings().model_copy(update={"use_redis_seat_lock": False})
    svc = SeatService(SeatRepository(), IdempotencyRepository(), settings, redis=fake_redis)
    with pytest.raises(SeatAlreadyHeldError):
        svc.confirm_seat(db_session, p2.id, st.id, "idem-other")
    # Transaction rolls back on error; in-memory expiry reset is not persisted.
    s2 = SessionLocal()
    try:
        st2 = s2.get(Seat, st.id)
        assert st2 is not None
        assert st2.status == SeatStatus.HELD
    finally:
        s2.close()
