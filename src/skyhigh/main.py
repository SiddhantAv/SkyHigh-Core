import logging
import time
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import JSONResponse

from skyhigh.api.v1.router import api_router
from skyhigh.config import get_settings
from skyhigh.exceptions import (
    CheckInSessionNotFoundError,
    IdempotencyKeyMismatchError,
    InvalidPaymentStateError,
    PassengerHoldRateLimitedError,
    SeatAlreadyConfirmedError,
    SeatAlreadyHeldError,
    SeatHoldExpiredError,
    SeatNotFoundError,
    SeatNotReadyForCheckInError,
    WeightServiceError,
)
from skyhigh.infrastructure.redis_client import close_redis, init_redis
from skyhigh.logging import configure_logging
from skyhigh.observability.middleware import RequestIdMiddleware
from skyhigh.observability.rate_limit import RateLimitMiddleware

log = logging.getLogger(__name__)


def _structured_error(
    exc: Exception,
    *,
    status_code: int,
    details: dict | None = None,
) -> JSONResponse:
    code = getattr(exc, "code", type(exc).__name__)
    message = getattr(exc, "message", str(exc))
    body: dict = {"error": code, "message": message}
    if details:
        body["details"] = details
    return JSONResponse(status_code=status_code, content=body)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    init_redis(settings.redis_url)
    log.info("Application startup complete")
    yield
    close_redis()
    log.info("Application shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="SkyHigh Core",
        description=(
            "Digital check-in API: concurrency-safe seat holds, Redis-backed seat maps, "
            "baggage rules, and simulated extra-baggage payment."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(RateLimitMiddleware, settings=settings)
    app.include_router(api_router, prefix="/api/v1")

    @app.exception_handler(SeatNotFoundError)
    async def _seat_not_found(_: Request, exc: SeatNotFoundError) -> JSONResponse:
        return _structured_error(exc, status_code=404, details={"seat_id": exc.seat_id})

    @app.exception_handler(SeatAlreadyHeldError)
    async def _seat_held(_: Request, exc: SeatAlreadyHeldError) -> JSONResponse:
        return _structured_error(exc, status_code=409)

    @app.exception_handler(SeatAlreadyConfirmedError)
    async def _seat_confirmed(_: Request, exc: SeatAlreadyConfirmedError) -> JSONResponse:
        return _structured_error(exc, status_code=409)

    @app.exception_handler(SeatHoldExpiredError)
    async def _seat_expired(_: Request, exc: SeatHoldExpiredError) -> JSONResponse:
        return _structured_error(exc, status_code=409)

    @app.exception_handler(SeatNotReadyForCheckInError)
    async def _not_ready(_: Request, exc: SeatNotReadyForCheckInError) -> JSONResponse:
        return _structured_error(exc, status_code=409)

    @app.exception_handler(CheckInSessionNotFoundError)
    async def _session_not_found(_: Request, exc: CheckInSessionNotFoundError) -> JSONResponse:
        return _structured_error(
            exc,
            status_code=404,
            details={"checkin_session_id": exc.session_id},
        )

    @app.exception_handler(InvalidPaymentStateError)
    async def _bad_payment(_: Request, exc: InvalidPaymentStateError) -> JSONResponse:
        return _structured_error(exc, status_code=409)

    @app.exception_handler(IdempotencyKeyMismatchError)
    async def _idem_mismatch(_: Request, exc: IdempotencyKeyMismatchError) -> JSONResponse:
        return _structured_error(exc, status_code=409)

    @app.exception_handler(PassengerHoldRateLimitedError)
    async def _passenger_hold_rl(_: Request, exc: PassengerHoldRateLimitedError) -> JSONResponse:
        retry_after = max(1, 60 - (int(time.time()) % 60))
        r = _structured_error(exc, status_code=429)
        r.headers["Retry-After"] = str(retry_after)
        return r

    @app.exception_handler(WeightServiceError)
    async def _weight_svc(_: Request, exc: WeightServiceError) -> JSONResponse:
        return _structured_error(exc, status_code=502)

    return app


app = create_app()
