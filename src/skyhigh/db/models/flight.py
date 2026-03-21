from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from skyhigh.db.base import Base


class Flight(Base):
    __tablename__ = "flights"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    flight_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    departure_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    seats: Mapped[list["Seat"]] = relationship(
        "Seat",
        back_populates="flight",
        cascade="all, delete-orphan",
    )
