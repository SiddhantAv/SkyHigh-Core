from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from skyhigh.db.base import Base


class IdempotencyKey(Base):
    """Stores idempotent hold responses (key unique per logical request)."""

    __tablename__ = "idempotency_keys"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False, index=True)
    response_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
