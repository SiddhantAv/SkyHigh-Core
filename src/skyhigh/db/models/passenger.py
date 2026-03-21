from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from skyhigh.db.base import Base


class Passenger(Base):
    __tablename__ = "passengers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    seats_held: Mapped[list["Seat"]] = relationship(
        "Seat",
        back_populates="held_by_passenger",
        foreign_keys="Seat.held_by",
    )
    checkin_sessions: Mapped[list["CheckInSession"]] = relationship(
        "CheckInSession",
        back_populates="passenger",
    )
