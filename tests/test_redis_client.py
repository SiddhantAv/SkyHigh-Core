"""Redis pool helpers (init / get / close)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import skyhigh.infrastructure.redis_client as redis_client


@pytest.fixture
def restore_pool_after_test() -> None:
    saved = redis_client._pool
    yield
    redis_client._pool = saved


def test_get_redis_raises_when_pool_missing(restore_pool_after_test: None) -> None:
    redis_client._pool = None
    with pytest.raises(RuntimeError, match="Redis not initialized"):
        redis_client.get_redis()


def test_init_redis_creates_pool_only_once(restore_pool_after_test: None) -> None:
    redis_client._pool = None
    fake_pool = MagicMock()
    with patch.object(redis_client.redis.ConnectionPool, "from_url", return_value=fake_pool) as m:
        redis_client.init_redis("redis://first")
        redis_client.init_redis("redis://second")
    assert m.call_count == 1
    assert redis_client._pool is fake_pool


def test_close_redis_disconnects_and_clears_pool(restore_pool_after_test: None) -> None:
    mock_pool = MagicMock()
    redis_client._pool = mock_pool
    redis_client.close_redis()
    mock_pool.disconnect.assert_called_once()
    assert redis_client._pool is None


def test_redis_from_settings_delegates_to_get_redis(restore_pool_after_test: None) -> None:
    mock_pool = MagicMock()
    redis_client._pool = mock_pool
    with patch.object(redis_client.redis, "Redis", return_value=MagicMock()) as m:
        c = redis_client.redis_from_settings()
    m.assert_called_once_with(connection_pool=mock_pool)
    assert c is m.return_value
