"""Redis seat-map cache helpers (failure-tolerant)."""

from unittest.mock import MagicMock

from skyhigh.infrastructure import cache


def test_get_seat_map_returns_none_when_redis_is_none() -> None:
    assert cache.get_seat_map(None, 1) is None


def test_get_seat_map_returns_none_on_invalid_json() -> None:
    r = MagicMock()
    r.get = MagicMock(return_value="not-json")
    assert cache.get_seat_map(r, 99) is None


def test_get_seat_map_returns_none_when_not_list() -> None:
    r = MagicMock()
    r.get = MagicMock(return_value='{"a": 1}')
    assert cache.get_seat_map(r, 1) is None


def test_get_seat_map_happy_path() -> None:
    r = MagicMock()
    r.get = MagicMock(return_value='[{"seat_id": 1, "seat_number": "1A", "status": "AVAILABLE"}]')
    out = cache.get_seat_map(r, 7)
    assert out is not None
    assert out[0]["seat_id"] == 1


def test_set_seat_map_swallows_errors() -> None:
    r = MagicMock()
    r.setex = MagicMock(side_effect=RuntimeError("boom"))
    cache.set_seat_map(r, 1, [], ttl_seconds=30)
    r.setex.assert_called_once()


def test_invalidate_seat_maps_dedupes() -> None:
    r = MagicMock()
    cache.invalidate_seat_maps(r, [1, 1, 2])
    assert r.delete.call_count == 2


def test_seat_map_key() -> None:
    assert cache.seat_map_key(42) == "seat_map:42"
