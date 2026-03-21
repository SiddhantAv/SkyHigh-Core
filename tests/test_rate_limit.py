"""Rate limit middleware and client IP extraction."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from skyhigh.config import get_settings
from skyhigh.observability.rate_limit import RateLimitMiddleware, _client_ip


def _http_scope(
    *,
    path: str = "/api/v1/ping",
    method: str = "GET",
    headers: list[tuple[bytes, bytes]] | None = None,
    client: tuple[str, int] | None = ("203.0.113.7", 1234),
) -> dict:
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "scheme": "http",
        "query_string": b"",
        "headers": headers or [],
        "client": client,
        "server": ("testserver", 80),
        "state": {},
    }


def test_client_ip_prefers_x_forwarded_for() -> None:
    req = Request(
        _http_scope(
            headers=[(b"x-forwarded-for", b"198.51.100.2, 10.0.0.1")],
        )
    )
    assert _client_ip(req) == "198.51.100.2"


def test_client_ip_x_forwarded_for_empty_falls_back_to_unknown() -> None:
    req = Request(_http_scope(headers=[(b"x-forwarded-for", b" , ")]))
    assert _client_ip(req) == "unknown"


def test_client_ip_uses_request_client_host() -> None:
    req = Request(_http_scope(client=("198.51.100.9", 0)))
    assert _client_ip(req) == "198.51.100.9"


def test_client_ip_unknown_when_no_forwarded_and_no_client() -> None:
    req = Request(_http_scope(client=None))
    assert _client_ip(req) == "unknown"


@pytest.fixture
def rate_limited_app() -> Starlette:
    async def ping(_: Request) -> JSONResponse:
        return JSONResponse({"ok": True})

    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    app = Starlette(
        routes=[
            Route("/api/v1/ping", ping, methods=["GET"]),
            Route("/api/v1/health/live", health, methods=["GET"]),
            Route("/other", ping, methods=["GET"]),
        ]
    )
    settings = get_settings().model_copy(
        update={
            "rate_limit_enabled": True,
            "rate_limit_get_per_minute": 2,
            "rate_limit_post_per_minute": 1,
        }
    )
    app.add_middleware(RateLimitMiddleware, settings=settings)
    return app


@patch("skyhigh.observability.rate_limit.get_redis")
def test_rate_limit_allows_under_limit(mock_get_redis: MagicMock, rate_limited_app: Starlette) -> None:
    r = MagicMock()
    r.incr = MagicMock(return_value=1)
    r.expire = MagicMock()
    mock_get_redis.return_value = r
    client = TestClient(rate_limited_app)
    assert client.get("/api/v1/ping").status_code == 200


@patch("skyhigh.observability.rate_limit.get_redis")
def test_rate_limit_returns_429_when_over_limit(mock_get_redis: MagicMock, rate_limited_app: Starlette) -> None:
    r = MagicMock()
    r.incr = MagicMock(return_value=3)
    r.expire = MagicMock()
    mock_get_redis.return_value = r
    client = TestClient(rate_limited_app)
    res = client.get("/api/v1/ping")
    assert res.status_code == 429
    assert res.headers.get("Retry-After") is not None


@patch("skyhigh.observability.rate_limit.get_redis")
def test_rate_limit_fails_open_on_redis_error(mock_get_redis: MagicMock, rate_limited_app: Starlette) -> None:
    mock_get_redis.side_effect = RuntimeError("redis down")
    client = TestClient(rate_limited_app)
    assert client.get("/api/v1/ping").status_code == 200


@patch("skyhigh.observability.rate_limit.get_redis")
def test_rate_limit_skips_non_api_paths(mock_get_redis: MagicMock, rate_limited_app: Starlette) -> None:
    mock_get_redis.side_effect = AssertionError("redis should not be used")
    client = TestClient(rate_limited_app)
    assert client.get("/other").status_code == 200


@patch("skyhigh.observability.rate_limit.get_redis")
def test_rate_limit_skips_health_paths(mock_get_redis: MagicMock, rate_limited_app: Starlette) -> None:
    mock_get_redis.side_effect = AssertionError("redis should not be used")
    client = TestClient(rate_limited_app)
    assert client.get("/api/v1/health/live").status_code == 200


@patch("skyhigh.observability.rate_limit.get_redis")
def test_rate_limit_skips_unsupported_methods(mock_get_redis: MagicMock, rate_limited_app: Starlette) -> None:
    mock_get_redis.side_effect = AssertionError("redis should not be used")
    client = TestClient(rate_limited_app)
    assert client.options("/api/v1/ping").status_code == 405


@patch("skyhigh.observability.rate_limit.get_redis")
def test_rate_limit_disabled_bypasses_redis(mock_get_redis: MagicMock) -> None:
    async def ping(_: Request) -> JSONResponse:
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/api/v1/ping", ping, methods=["GET"])])
    settings = get_settings().model_copy(update={"rate_limit_enabled": False})
    app.add_middleware(RateLimitMiddleware, settings=settings)
    mock_get_redis.side_effect = AssertionError("redis should not be used")
    client = TestClient(app)
    assert client.get("/api/v1/ping").status_code == 200


@patch("skyhigh.observability.rate_limit.get_redis")
def test_rate_limit_post_uses_post_bucket(mock_get_redis: MagicMock) -> None:
    async def echo(request: Request) -> JSONResponse:
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/api/v1/ping", echo, methods=["POST"])])
    settings = get_settings().model_copy(
        update={
            "rate_limit_enabled": True,
            "rate_limit_get_per_minute": 100,
            "rate_limit_post_per_minute": 1,
        }
    )
    app.add_middleware(RateLimitMiddleware, settings=settings)
    r = MagicMock()
    r.incr = MagicMock(return_value=2)
    r.expire = MagicMock()
    mock_get_redis.return_value = r
    client = TestClient(app)
    assert client.post("/api/v1/ping").status_code == 429
