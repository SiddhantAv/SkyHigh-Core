import logging
from typing import Optional

import redis

log = logging.getLogger(__name__)

_pool: Optional[redis.ConnectionPool] = None


def init_redis(url: str) -> None:
    """Create a process-wide connection pool (call from app lifespan)."""
    global _pool
    if _pool is not None:
        return
    _pool = redis.ConnectionPool.from_url(
        url,
        decode_responses=True,
        max_connections=50,
    )
    log.info("Redis connection pool initialized")


def close_redis() -> None:
    global _pool
    if _pool is not None:
        _pool.disconnect()
        _pool = None
        log.info("Redis connection pool closed")


def get_redis() -> redis.Redis:
    """Return a client bound to the shared pool (thread-safe for single commands)."""
    if _pool is None:
        raise RuntimeError("Redis not initialized; call init_redis() on startup")
    return redis.Redis(connection_pool=_pool)


def redis_from_settings() -> redis.Redis:
    """Convenience for dependencies when pool is already initialized."""
    return get_redis()
