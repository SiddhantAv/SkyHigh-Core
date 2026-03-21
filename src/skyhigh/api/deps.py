from typing import Annotated

from fastapi import Depends
from redis import Redis
from sqlalchemy.orm import Session

from skyhigh.config import get_settings
from skyhigh.db.session import get_db
from skyhigh.infrastructure.redis_client import get_redis
from skyhigh.repositories.checkin_repository import CheckinRepository
from skyhigh.repositories.idempotency_repository import IdempotencyRepository
from skyhigh.repositories.seat_repository import SeatRepository
from skyhigh.services.checkin_service import CheckinService
from skyhigh.services.seat_service import SeatService

DbSession = Annotated[Session, Depends(get_db)]


def get_redis_client() -> Redis:
    return get_redis()


RedisDep = Annotated[Redis, Depends(get_redis_client)]


def get_seat_service(redis: RedisDep) -> SeatService:
    return SeatService(
        SeatRepository(),
        IdempotencyRepository(),
        get_settings(),
        redis,
    )


SeatServiceDep = Annotated[SeatService, Depends(get_seat_service)]


def get_checkin_service() -> CheckinService:
    return CheckinService(
        CheckinRepository(),
        SeatRepository(),
        get_settings(),
    )


CheckinServiceDep = Annotated[CheckinService, Depends(get_checkin_service)]
