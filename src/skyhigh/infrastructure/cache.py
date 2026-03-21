"""Redis seat-map cache (DB remains authoritative; failures fall back to DB)."""

from __future__ import annotations

import json
import logging
from typing import Any

log = logging.getLogger(__name__)

SEAT_MAP_PREFIX = "seat_map:"


def seat_map_key(flight_id: int) -> str:
    return f"{SEAT_MAP_PREFIX}{flight_id}"


def get_seat_map(redis: Any | None, flight_id: int) -> list[dict[str, Any]] | None:
    if redis is None:
        return None
    try:
        raw = redis.get(seat_map_key(flight_id))
        if raw is None:
            return None
        data = json.loads(raw)
        if not isinstance(data, list):
            return None
        return data
    except Exception:
        log.warning("seat map cache read failed flight_id=%s", flight_id, exc_info=True)
        return None


def set_seat_map(
    redis: Any | None,
    flight_id: int,
    data: list[dict[str, Any]],
    ttl_seconds: int,
) -> None:
    if redis is None:
        return
    try:
        redis.setex(seat_map_key(flight_id), ttl_seconds, json.dumps(data))
    except Exception:
        log.warning("seat map cache write failed flight_id=%s", flight_id, exc_info=True)


def invalidate_seat_map(redis: Any | None, flight_id: int) -> None:
    if redis is None:
        return
    try:
        redis.delete(seat_map_key(flight_id))
    except Exception:
        log.warning("seat map cache invalidate failed flight_id=%s", flight_id, exc_info=True)


def invalidate_seat_maps(redis: Any | None, flight_ids: list[int]) -> None:
    if redis is None or not flight_ids:
        return
    seen: set[int] = set()
    for fid in flight_ids:
        if fid in seen:
            continue
        seen.add(fid)
        invalidate_seat_map(redis, fid)
