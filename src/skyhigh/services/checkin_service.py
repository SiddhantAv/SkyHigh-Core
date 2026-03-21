from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from skyhigh.config import Settings
from skyhigh.db.models import CheckInSession
from skyhigh.db.models.enums import CheckInStatus, PaymentStatus, SeatStatus
from skyhigh.exceptions import (
    CheckInSessionNotFoundError,
    InvalidPaymentStateError,
    SeatNotReadyForCheckInError,
    WeightServiceError,
)
from skyhigh.repositories.checkin_repository import CheckinRepository
from skyhigh.repositories.seat_repository import SeatRepository

log = logging.getLogger(__name__)


class CheckinService:
    """Baggage rules + simulated payment for check-in sessions."""

    def __init__(
        self,
        checkin_repo: CheckinRepository,
        seat_repo: SeatRepository,
        settings: Settings,
    ) -> None:
        self._checkin = checkin_repo
        self._seats = seat_repo
        self._settings = settings

    def _envelope(self, status: str, message: str, data: dict[str, Any] | None) -> dict[str, Any]:
        return {"status": status, "message": message, "data": data}

    def _resolve_baggage_kg(self, passenger_id: int, declared_kg: float) -> Decimal:
        url = self._settings.weight_service_url
        if not url or not url.strip():
            return Decimal(str(declared_kg))
        payload = json.dumps(
            {"passenger_id": passenger_id, "declared_kg": declared_kg},
        ).encode()
        req = urllib.request.Request(
            url.strip(),
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            timeout = self._settings.weight_service_timeout_seconds
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode())
            v = body.get("verified_kg")
            if v is None:
                raise WeightServiceError("Weight service response missing verified_kg.")
            return Decimal(str(v))
        except WeightServiceError:
            raise
        except urllib.error.HTTPError as e:
            raise WeightServiceError(f"Weight service HTTP {e.code}.") from e
        except urllib.error.URLError as e:
            raise WeightServiceError(str(e.reason)) from e
        except Exception as e:
            log.warning("weight service error", exc_info=True)
            raise WeightServiceError(str(e)) from e

    def start_checkin(
        self,
        session: Session,
        passenger_id: int,
        seat_id: int,
        baggage_weight: float,
    ) -> dict[str, Any]:
        weight = self._resolve_baggage_kg(passenger_id, baggage_weight)
        max_kg = Decimal(str(self._settings.max_baggage_kg))

        with session.begin():
            seat = self._seats.get_seat_by_id(session, seat_id)
            if seat is None:
                raise SeatNotReadyForCheckInError("The selected seat does not exist.")

            if seat.status != SeatStatus.CONFIRMED:
                raise SeatNotReadyForCheckInError(
                    "Your seat must be confirmed before you can check in."
                )

            if seat.held_by != passenger_id:
                raise SeatNotReadyForCheckInError(
                    "This confirmed seat is not assigned to you."
                )

            existing = self._checkin.get_latest_by_passenger_seat(session, passenger_id, seat_id)
            if existing is not None:
                if existing.status == CheckInStatus.COMPLETED:
                    return self._envelope(
                        CheckInStatus.COMPLETED.value,
                        "Check-in is already completed for this seat.",
                        {
                            "checkin_session_id": existing.id,
                            "baggage_weight": float(existing.baggage_weight)
                            if existing.baggage_weight is not None
                            else None,
                        },
                    )
                if existing.status == CheckInStatus.WAITING_FOR_PAYMENT:
                    return self._envelope(
                        CheckInStatus.WAITING_FOR_PAYMENT.value,
                        f"Baggage exceeds {self._settings.max_baggage_kg:g} kg. "
                        "Please complete payment to continue check-in.",
                        {
                            "checkin_session_id": existing.id,
                            "baggage_weight": float(existing.baggage_weight)
                            if existing.baggage_weight is not None
                            else float(weight),
                        },
                    )
                if existing.status == CheckInStatus.IN_PROGRESS:
                    existing.baggage_weight = weight
                    if weight > max_kg:
                        existing.status = CheckInStatus.WAITING_FOR_PAYMENT
                        existing.payment_status = PaymentStatus.PENDING
                        session.add(existing)
                        return self._envelope(
                            CheckInStatus.WAITING_FOR_PAYMENT.value,
                            f"Baggage exceeds {self._settings.max_baggage_kg:g} kg. "
                            "Please complete payment to continue check-in.",
                            {
                                "checkin_session_id": existing.id,
                                "baggage_weight": float(weight),
                            },
                        )
                    session.add(existing)
                    return self._envelope(
                        CheckInStatus.IN_PROGRESS.value,
                        "Check-in in progress. Baggage updated; call POST /checkin/complete when ready.",
                        {
                            "checkin_session_id": existing.id,
                            "baggage_weight": float(weight),
                        },
                    )

            if weight > max_kg:
                row = CheckInSession(
                    passenger_id=passenger_id,
                    seat_id=seat_id,
                    status=CheckInStatus.WAITING_FOR_PAYMENT,
                    baggage_weight=weight,
                    payment_status=PaymentStatus.PENDING,
                )
                self._checkin.add_session(session, row)
                return self._envelope(
                    CheckInStatus.WAITING_FOR_PAYMENT.value,
                    f"Baggage exceeds {self._settings.max_baggage_kg:g} kg. "
                    "Please complete payment to continue check-in.",
                    {
                        "checkin_session_id": row.id,
                        "baggage_weight": float(weight),
                    },
                )

            row = CheckInSession(
                passenger_id=passenger_id,
                seat_id=seat_id,
                status=CheckInStatus.IN_PROGRESS,
                baggage_weight=weight,
                payment_status=PaymentStatus.PENDING,
            )
            self._checkin.add_session(session, row)
            return self._envelope(
                CheckInStatus.IN_PROGRESS.value,
                f"Check-in started. Baggage is within the allowed {self._settings.max_baggage_kg:g} kg. "
                "Call POST /checkin/complete to finish check-in.",
                {
                    "checkin_session_id": row.id,
                    "baggage_weight": float(weight),
                },
            )

    def complete_checkin(
        self,
        session: Session,
        passenger_id: int,
        seat_id: int,
    ) -> dict[str, Any]:
        with session.begin():
            seat = self._seats.get_seat_by_id(session, seat_id)
            if seat is None:
                raise SeatNotReadyForCheckInError("The selected seat does not exist.")

            if seat.status != SeatStatus.CONFIRMED:
                raise SeatNotReadyForCheckInError(
                    "Your seat must be confirmed before you can check in."
                )

            if seat.held_by != passenger_id:
                raise SeatNotReadyForCheckInError(
                    "This confirmed seat is not assigned to you."
                )

            existing = self._checkin.get_latest_by_passenger_seat(session, passenger_id, seat_id)
            if existing is None:
                raise SeatNotReadyForCheckInError(
                    "Start check-in first with POST /checkin/start before completing."
                )

            if existing.status == CheckInStatus.COMPLETED:
                return self._envelope(
                    CheckInStatus.COMPLETED.value,
                    "Check-in is already completed for this seat.",
                    {
                        "checkin_session_id": existing.id,
                        "baggage_weight": float(existing.baggage_weight)
                        if existing.baggage_weight is not None
                        else None,
                    },
                )

            if existing.status == CheckInStatus.WAITING_FOR_PAYMENT:
                raise InvalidPaymentStateError(
                    "Extra baggage payment is required. Use POST /checkin/payment first."
                )

            if existing.status != CheckInStatus.IN_PROGRESS:
                raise InvalidPaymentStateError("Check-in cannot be completed in its current state.")

            existing.status = CheckInStatus.COMPLETED
            existing.payment_status = PaymentStatus.PAID
            session.add(existing)
            completed_id = existing.id
            bw = existing.baggage_weight

        return self._envelope(
            CheckInStatus.COMPLETED.value,
            "Check-in completed.",
            {
                "checkin_session_id": completed_id,
                "baggage_weight": float(bw) if bw is not None else None,
            },
        )

    def complete_payment(self, session: Session, checkin_session_id: int) -> dict[str, Any]:
        completed_id: int
        with session.begin():
            row = self._checkin.get_session_by_id(session, checkin_session_id)
            if row is None:
                raise CheckInSessionNotFoundError(checkin_session_id)

            if row.status != CheckInStatus.WAITING_FOR_PAYMENT:
                raise InvalidPaymentStateError(
                    "Extra baggage payment is not required for this check-in."
                )

            row.payment_status = PaymentStatus.PAID
            row.status = CheckInStatus.COMPLETED
            session.add(row)
            completed_id = row.id

        return self._envelope(
            CheckInStatus.COMPLETED.value,
            "Payment successful. Check-in completed.",
            {"checkin_session_id": completed_id},
        )
