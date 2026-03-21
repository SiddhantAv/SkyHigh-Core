from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from skyhigh.db.base import Base
from skyhigh.db.models.enums import CheckInStatus, PaymentStatus


class CheckInSession(Base):
    """
    Check-in workflow state: baggage + payment pause without overloading Seat.
    """

    __tablename__ = "checkin_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    passenger_id: Mapped[int] = mapped_column(
        ForeignKey("passengers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seat_id: Mapped[int] = mapped_column(
        ForeignKey("seats.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[CheckInStatus] = mapped_column(
        Enum(CheckInStatus, name="checkin_status", native_enum=True, create_constraint=True),
        nullable=False,
        default=CheckInStatus.IN_PROGRESS,
    )
    baggage_weight: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    payment_status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status", native_enum=True, create_constraint=True),
        nullable=False,
        default=PaymentStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    passenger: Mapped["Passenger"] = relationship(
        "Passenger",
        back_populates="checkin_sessions",
    )
    seat: Mapped["Seat"] = relationship("Seat", back_populates="checkin_sessions")
