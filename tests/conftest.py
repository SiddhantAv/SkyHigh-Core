"""
Test bootstrap: set DATABASE_URL before any skyhigh import (session binds engine at import).
Uses in-memory SQLite + StaticPool (see db/session.py) so all connections share one DB.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ["WEIGHT_SERVICE_URL"] = ""
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["PASSENGER_HOLD_RATE_LIMIT_ENABLED"] = "false"

import skyhigh.db.models  # noqa: E402  # register metadata
from skyhigh.api.deps import get_redis_client  # noqa: E402
from skyhigh.config import get_settings  # noqa: E402
from skyhigh.db.base import Base  # noqa: E402
from skyhigh.db.session import SessionLocal, engine, get_db  # noqa: E402
from skyhigh.main import app  # noqa: E402

get_settings.cache_clear()


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def fake_redis() -> MagicMock:
    r = MagicMock()
    r.ping = MagicMock(return_value=True)
    r.get = MagicMock(return_value=None)
    r.setex = MagicMock()
    r.delete = MagicMock()

    lock_cm = MagicMock()
    lock_cm.__enter__ = MagicMock(return_value=None)
    lock_cm.__exit__ = MagicMock(return_value=False)
    r.lock = MagicMock(return_value=lock_cm)
    return r


@pytest.fixture
def client(db_session: Session, fake_redis: MagicMock) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    def override_redis() -> MagicMock:
        return fake_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis_client] = override_redis
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def checkin_world(db_session: Session) -> dict[str, int]:
    from datetime import datetime, timezone

    from skyhigh.db.models import Flight, Passenger, Seat
    from skyhigh.db.models.enums import SeatStatus

    fl = Flight(flight_number="SK1", departure_time=datetime.now(timezone.utc))
    db_session.add(fl)
    db_session.flush()
    p = Passenger(name="Test User")
    db_session.add(p)
    db_session.flush()
    st = Seat(
        flight_id=fl.id,
        seat_number="1A",
        status=SeatStatus.CONFIRMED,
        held_by=p.id,
        held_until=None,
    )
    db_session.add(st)
    db_session.commit()
    return {"flight_id": fl.id, "passenger_id": p.id, "seat_id": st.id}
