"""Database-facing enums (Python Enum + SQLAlchemy-compatible values)."""

from enum import Enum


class SeatStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    HELD = "HELD"
    CONFIRMED = "CONFIRMED"


class CheckInStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_FOR_PAYMENT = "WAITING_FOR_PAYMENT"
    COMPLETED = "COMPLETED"


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
