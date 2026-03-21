"""Worker entrypoints (batch expiry loop, idempotency TTL cleanup)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import update

from skyhigh.config import Settings, get_settings
from skyhigh.db.models import IdempotencyKey
from skyhigh.workers import expiry_worker
from skyhigh.workers.idempotency_cleanup_worker import run_idempotency_cleanup


def test_workers_package_exports() -> None:
    import skyhigh.workers as workers

    assert set(workers.__all__) == {
        "expire_held_seats_once",
        "run_idempotency_cleanup",
        "run_seat_expiry_job",
    }


@patch("skyhigh.workers.expiry_worker.invalidate_seat_maps")
def test_run_seat_expiry_job_batches_until_empty(mock_invalidate: MagicMock, db_session) -> None:
    with patch.object(expiry_worker, "SeatRepository") as RepoCls:
        inst = MagicMock()
        inst.reset_expired_held_seats_batch.side_effect = [[10, 10], []]
        RepoCls.return_value = inst
        settings = Settings.model_construct(
            database_url="sqlite://",
            redis_url="redis://",
            seat_expiry_batch_size=100,
        )
        total = expiry_worker.run_seat_expiry_job(
            db_session,
            settings,
            redis=None,
            now_utc=datetime.now(timezone.utc),
            max_rounds=10,
        )
    assert total == 2
    assert mock_invalidate.call_count == 1
    mock_invalidate.assert_called_with(None, [10, 10])


@patch("skyhigh.workers.expiry_worker.invalidate_seat_maps")
@patch("skyhigh.workers.expiry_worker.get_settings")
def test_expire_held_seats_once_delegates(mock_gs: MagicMock, _inv: MagicMock, db_session) -> None:
    mock_gs.return_value = Settings.model_construct(
        database_url="sqlite://",
        redis_url="redis://",
        seat_expiry_batch_size=50,
    )
    with patch.object(expiry_worker, "SeatRepository") as RepoCls:
        inst = MagicMock()
        inst.reset_expired_held_seats_batch.return_value = []
        RepoCls.return_value = inst
        n = expiry_worker.expire_held_seats_once(db_session, redis=None)
    assert n == 0


def test_run_idempotency_cleanup_deletes_stale_rows(db_session) -> None:
    row = IdempotencyKey(key="stale-key", response_data=None)
    db_session.add(row)
    db_session.commit()
    old = datetime.now(timezone.utc) - timedelta(days=2)
    db_session.execute(update(IdempotencyKey).where(IdempotencyKey.id == row.id).values(created_at=old))
    db_session.commit()

    settings = get_settings().model_copy(update={"idempotency_ttl_hours": 24})
    removed = run_idempotency_cleanup(db_session, settings)
    assert removed >= 1
    db_session.expire_all()
    assert db_session.get(IdempotencyKey, row.id) is None


def test_run_idempotency_cleanup_keeps_recent_rows(db_session) -> None:
    row = IdempotencyKey(key="fresh-key", response_data=None)
    db_session.add(row)
    db_session.flush()
    db_session.execute(
        update(IdempotencyKey)
        .where(IdempotencyKey.id == row.id)
        .values(created_at=datetime.now(timezone.utc)),
    )
    db_session.commit()
    settings = get_settings().model_copy(update={"idempotency_ttl_hours": 24})
    removed = run_idempotency_cleanup(db_session, settings)
    assert removed == 0
    assert db_session.get(IdempotencyKey, row.id) is not None


@patch("skyhigh.workers.expiry_loop.close_redis")
@patch("skyhigh.workers.expiry_loop.time.sleep", side_effect=KeyboardInterrupt)
@patch("skyhigh.workers.expiry_loop.run_seat_expiry_job", return_value=2)
@patch("skyhigh.workers.expiry_loop.get_redis")
@patch("skyhigh.workers.expiry_loop.init_redis")
@patch("skyhigh.workers.expiry_loop.SessionLocal")
@patch("skyhigh.workers.expiry_loop.get_settings")
def test_expiry_loop_main_runs_batch_then_stops_on_interrupt(
    mock_get_settings: MagicMock,
    mock_session_local: MagicMock,
    mock_init_redis: MagicMock,
    mock_get_redis: MagicMock,
    mock_run_job: MagicMock,
    _mock_sleep: MagicMock,
    mock_close_redis: MagicMock,
) -> None:
    from skyhigh.workers import expiry_loop

    sess_cm = MagicMock()
    sess_cm.__enter__.return_value = MagicMock()
    sess_cm.__exit__.return_value = False
    mock_session_local.return_value = sess_cm

    s = MagicMock()
    s.log_level = "WARNING"
    s.redis_url = "redis://localhost:6379/0"
    s.seat_expiry_worker_interval_seconds = 1
    mock_get_settings.return_value = s

    with pytest.raises(KeyboardInterrupt):
        expiry_loop.main()

    mock_init_redis.assert_called_once_with(s.redis_url)
    mock_run_job.assert_called_once()
    mock_close_redis.assert_called_once()
