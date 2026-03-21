from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

from skyhigh.api.deps import DbSession, RedisDep
from skyhigh.api.schemas.health import HealthApiResponse, ReadyApiResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthApiResponse,
    summary="Liveness probe",
    description="Returns **200** when the API process is up. Does not check databases.",
)
def health() -> HealthApiResponse:
    return HealthApiResponse(
        status="ok",
        message="SkyHigh Core is running.",
        data=None,
    )


@router.get(
    "/health/ready",
    response_model=ReadyApiResponse,
    summary="Readiness probe",
    description="Verifies connectivity to **PostgreSQL** and **Redis**.",
)
def ready(
    db: DbSession,
    redis_client: RedisDep,
) -> ReadyApiResponse:
    db.execute(text("SELECT 1"))
    redis_client.ping()
    details: dict[str, Any] = {"database": "ok", "redis": "ok"}
    return ReadyApiResponse(
        status="ready",
        message="Database and Redis are reachable.",
        data=details,
    )
