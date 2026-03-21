from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from skyhigh.db.base import Base
from skyhigh.db.models.enums import SeatStatus


class Seat(Base):
    """
    Single source of truth for seat state. Holds are represented in-row
    (no separate hold table): status + held_by + held_until.
    """

    __tablename__ = "seats"
    __table_args__ = (
        UniqueConstraint("flight_id", "seat_number", name="uq_seats_flight_seat_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    flight_id: Mapped[int] = mapped_column(
        ForeignKey("flights.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seat_number: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[SeatStatus] = mapped_column(
        Enum(SeatStatus, name="seat_status", native_enum=True, create_constraint=True),
        nullable=False,
        default=SeatStatus.AVAILABLE,
    )
    held_by: Mapped[int | None] = mapped_column(
        ForeignKey("passengers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    held_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    flight: Mapped["Flight"] = relationship("Flight", back_populates="seats")
    held_by_passenger: Mapped["Passenger | None"] = relationship(
        "Passenger",
        back_populates="seats_held",
        foreign_keys=[held_by],
    )
    checkin_sessions: Mapped[list["CheckInSession"]] = relationship(
        "CheckInSession",
        back_populates="seat",
    )
