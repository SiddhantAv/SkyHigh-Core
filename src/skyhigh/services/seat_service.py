from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from redis import Redis
from sqlalchemy.orm import Session

from skyhigh.config import Settings
from skyhigh.exceptions import (
    IdempotencyKeyMismatchError,
    PassengerHoldRateLimitedError,
    SeatAlreadyConfirmedError,
    SeatAlreadyHeldError,
    SeatHoldExpiredError,
    SeatNotFoundError,
)

log = logging.getLogger(__name__)
from skyhigh.infrastructure.cache import get_seat_map as cache_get_seat_map
from skyhigh.infrastructure.cache import invalidate_seat_map
from skyhigh.infrastructure.cache import set_seat_map as cache_set_seat_map
from skyhigh.infrastructure.seat_redis_lock import optional_seat_lock
from skyhigh.db.models.enums import SeatStatus
from skyhigh.repositories.idempotency_repository import IdempotencyRepository
from skyhigh.repositories.seat_repository import SeatRepository

_MSG_HOLD_IDEMPOTENT = "This request was already processed. Returning the same reservation."
_MSG_CONFIRM_SUCCESS = "Your seat is now confirmed. You can proceed to check-in."
_MSG_CONFIRM_IDEMPOTENT = "This request was already processed. Returning the same confirmation."


def _hold_duration_phrase(seconds: int) -> str:
    if seconds <= 0:
        return "a short time"
    if seconds % 3600 == 0 and seconds // 3600 == 1:
        return "1 hour"
    if seconds % 3600 == 0:
        return f"{seconds // 3600} hours"
    if seconds % 60 == 0 and seconds // 60 == 1:
        return "1 minute"
    if seconds % 60 == 0:
        return f"{seconds // 60} minutes"
    return f"{seconds} seconds"


class SeatService:
    """Seat lifecycle + cached seat map — DB is source of truth."""

    def __init__(
        self,
        seat_repo: SeatRepository,
        idempotency_repo: IdempotencyRepository,
        settings: Settings,
        redis: Redis | None = None,
    ) -> None:
        self._seats = seat_repo
        self._idempotency = idempotency_repo
        self._settings = settings
        self._redis = redis

    def _enforce_passenger_hold_limit(self, passenger_id: int) -> None:
        if not self._settings.passenger_hold_rate_limit_enabled or self._redis is None:
            return
        try:
            bucket = int(time.time()) // 60
            key = f"skyhigh:hold:passenger:{passenger_id}:{bucket}"
            n = int(self._redis.incr(key))
            if n == 1:
                self._redis.expire(key, 120)
            if n > self._settings.passenger_hold_rate_per_minute:
                raise PassengerHoldRateLimitedError()
        except PassengerHoldRateLimitedError:
            raise
        except Exception:
            log.warning("passenger hold rate limit skipped", exc_info=True)

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _hold_envelope(
        *,
        seat_status: str,
        message: str,
        seat_id: int,
        held_until: str | None,
    ) -> dict[str, Any]:
        return {
            "status": seat_status,
            "message": message,
            "data": {"seat_id": seat_id, "held_until": held_until},
        }

    @staticmethod
    def _confirm_envelope(*, seat_status: str, message: str, seat_id: int) -> dict[str, Any]:
        return {
            "status": seat_status,
            "message": message,
            "data": {"seat_id": seat_id},
        }

    @staticmethod
    def _normalize_hold_idem(payload: dict[str, Any]) -> dict[str, Any]:
        if "seat_status" in payload:
            return payload
        return {
            "seat_id": int(payload["seat_id"]),
            "held_until": payload.get("held_until"),
            "seat_status": str(payload.get("status", "HELD")),
        }

    @staticmethod
    def _normalize_confirm_idem(payload: dict[str, Any]) -> dict[str, Any]:
        if "seat_status" in payload:
            return payload
        return {
            "seat_id": int(payload["seat_id"]),
            "seat_status": str(payload.get("status", "CONFIRMED")),
        }

    def get_seat_map(self, session: Session, flight_id: int) -> list[dict[str, Any]]:
        now = self._utcnow()
        with session.begin():
            expired = self._seats.reset_expired_held_seats_for_flight(session, flight_id, now)
        if expired > 0:
            invalidate_seat_map(self._redis, flight_id)
        cached = cache_get_seat_map(self._redis, flight_id)
        if cached is not None:
            return cached
        with session.begin():
            rows = self._seats.get_seat_map_by_flight(session, flight_id)
        cache_set_seat_map(
            self._redis,
            flight_id,
            rows,
            self._settings.seat_map_cache_ttl_seconds,
        )
        return rows

    def hold_seat(
        self,
        session: Session,
        passenger_id: int,
        seat_id: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        invalidate_flight_id: int | None = None
        out: dict[str, Any]
        with optional_seat_lock(
            self._redis,
            seat_id,
            enabled=self._settings.use_redis_seat_lock,
        ):
            with session.begin():
                idem = self._idempotency.get_or_create_for_update(session, idempotency_key)
                if idem.response_data is not None:
                    inner = self._normalize_hold_idem(dict(idem.response_data))
                    if int(inner["seat_id"]) != seat_id:
                        raise IdempotencyKeyMismatchError()
                    hu = inner.get("held_until")
                    if hu is not None and not isinstance(hu, str):
                        hu = str(hu)
                    return self._hold_envelope(
                        seat_status=inner["seat_status"],
                        message=_MSG_HOLD_IDEMPOTENT,
                        seat_id=int(inner["seat_id"]),
                        held_until=hu,
                    )

                self._enforce_passenger_hold_limit(passenger_id)

                now = self._utcnow()
                seat = self._seats.get_seat_for_update(session, seat_id)
                if seat is None:
                    raise SeatNotFoundError(seat_id)

                self._seats.reset_expired_seat_if_needed(session, seat, now)

                if seat.status == SeatStatus.CONFIRMED:
                    raise SeatAlreadyConfirmedError()

                if seat.status == SeatStatus.HELD:
                    raise SeatAlreadyHeldError()

                if seat.status != SeatStatus.AVAILABLE:
                    raise SeatAlreadyHeldError()

                hold_until = now + timedelta(seconds=self._settings.hold_duration_seconds)
                seat.status = SeatStatus.HELD
                seat.held_by = passenger_id
                seat.held_until = hold_until
                self._seats.update_seat(session, seat)

                held_iso = seat.held_until.isoformat() if seat.held_until is not None else None
                idem_payload = {
                    "seat_id": seat.id,
                    "held_until": held_iso,
                    "seat_status": seat.status.value,
                }
                idem.response_data = idem_payload
                invalidate_flight_id = seat.flight_id
                dur = _hold_duration_phrase(self._settings.hold_duration_seconds)
                out = self._hold_envelope(
                    seat_status=seat.status.value,
                    message=(
                        f"Seat successfully reserved for {dur}. "
                        "Complete your booking before it expires."
                    ),
                    seat_id=seat.id,
                    held_until=held_iso,
                )

        if invalidate_flight_id is not None:
            invalidate_seat_map(self._redis, invalidate_flight_id)
        return out

    def confirm_seat(
        self,
        session: Session,
        passenger_id: int,
        seat_id: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        invalidate_flight_id: int | None = None
        out: dict[str, Any]
        with optional_seat_lock(
            self._redis,
            seat_id,
            enabled=self._settings.use_redis_seat_lock,
        ):
            with session.begin():
                idem = self._idempotency.get_or_create_for_update(session, idempotency_key)
                if idem.response_data is not None:
                    inner = self._normalize_confirm_idem(dict(idem.response_data))
                    if int(inner["seat_id"]) != seat_id:
                        raise IdempotencyKeyMismatchError()
                    return self._confirm_envelope(
                        seat_status=inner["seat_status"],
                        message=_MSG_CONFIRM_IDEMPOTENT,
                        seat_id=int(inner["seat_id"]),
                    )

                now = self._utcnow()
                seat = self._seats.get_seat_for_update(session, seat_id)
                if seat is None:
                    raise SeatNotFoundError(seat_id)

                if seat.status == SeatStatus.CONFIRMED:
                    raise SeatAlreadyConfirmedError()

                if seat.status == SeatStatus.HELD and (
                    seat.held_until is None or seat.held_until < now
                ):
                    if seat.held_by == passenger_id:
                        self._seats.reset_expired_seat_if_needed(session, seat, now)
                        raise SeatHoldExpiredError()
                    self._seats.reset_expired_seat_if_needed(session, seat, now)

                if seat.status != SeatStatus.HELD:
                    raise SeatAlreadyHeldError()

                if seat.held_by != passenger_id:
                    raise SeatAlreadyHeldError()

                seat.status = SeatStatus.CONFIRMED
                seat.held_until = None
                self._seats.update_seat(session, seat)

                idem_payload = {
                    "seat_id": seat.id,
                    "seat_status": seat.status.value,
                }
                idem.response_data = idem_payload
                invalidate_flight_id = seat.flight_id
                out = self._confirm_envelope(
                    seat_status=seat.status.value,
                    message=_MSG_CONFIRM_SUCCESS,
                    seat_id=seat.id,
                )

        if invalidate_flight_id is not None:
            invalidate_seat_map(self._redis, invalidate_flight_id)
        return out
