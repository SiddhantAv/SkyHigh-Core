"""ORM models — import side effects register tables on Base.metadata."""

from skyhigh.db.models.checkin_session import CheckInSession
from skyhigh.db.models.enums import CheckInStatus, PaymentStatus, SeatStatus
from skyhigh.db.models.flight import Flight
from skyhigh.db.models.idempotency_key import IdempotencyKey
from skyhigh.db.models.passenger import Passenger
from skyhigh.db.models.seat import Seat

__all__ = [
    "CheckInSession",
    "CheckInStatus",
    "Flight",
    "IdempotencyKey",
    "Passenger",
    "PaymentStatus",
    "Seat",
    "SeatStatus",
]
