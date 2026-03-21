"""Per-IP fixed-window limits (Redis). Fails open if Redis is unavailable."""

import logging
import time
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from skyhigh.config import Settings, get_settings
from skyhigh.infrastructure.redis_client import get_redis

log = logging.getLogger(__name__)

_XFF = "x-forwarded-for"


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get(_XFF)
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    if request.client:
        return request.client.host
    return "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """GET and POST limits per client IP per minute (separate counters)."""

    def __init__(self, app, settings: Settings | None = None) -> None:
        super().__init__(app)
        self._settings = settings

    def _settings_resolved(self) -> Settings:
        return self._settings if self._settings is not None else get_settings()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Response],
    ) -> Response:
        settings = self._settings_resolved()
        path = request.url.path
        if not settings.rate_limit_enabled or not path.startswith("/api/v1"):
            return await call_next(request)
        if path.startswith("/api/v1/health"):
            return await call_next(request)

        method = request.method.upper()
        if method not in ("GET", "HEAD", "POST"):
            return await call_next(request)

        bucket_method = "POST" if method == "POST" else "GET"
        limit = (
            settings.rate_limit_post_per_minute
            if bucket_method == "POST"
            else settings.rate_limit_get_per_minute
        )
        bucket = int(time.time()) // 60
        client = _client_ip(request)
        key = f"rl:skyhigh:{bucket_method}:{client}:{bucket}"

        try:
            r = get_redis()
            n = int(r.incr(key))
            if n == 1:
                r.expire(key, 120)
            if n > limit:
                retry_after = max(1, 60 - (int(time.time()) % 60))
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "TooManyRequests",
                        "message": "Too many requests from this client. Please slow down and try again.",
                    },
                    headers={"Retry-After": str(retry_after)},
                )
        except Exception:
            log.warning("rate limit check skipped (redis error)", exc_info=True)

        return await call_next(request)
