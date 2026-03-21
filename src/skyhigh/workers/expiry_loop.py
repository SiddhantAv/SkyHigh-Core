"""Background loop: expire stale HELD seats in batches (run beside API or as cron)."""

from __future__ import annotations

import logging
import time

from skyhigh.config import get_settings
from skyhigh.db.session import SessionLocal
from skyhigh.infrastructure.redis_client import close_redis, get_redis, init_redis
from skyhigh.workers.expiry_worker import run_seat_expiry_job

log = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    init_redis(settings.redis_url)
    interval = max(1, settings.seat_expiry_worker_interval_seconds)
    try:
        while True:
            n = 0
            try:
                with SessionLocal() as session:
                    n = run_seat_expiry_job(session, settings, redis=get_redis())
            except Exception:
                log.exception("seat expiry batch failed")
            if n:
                log.info("released %s expired seat holds", n)
            time.sleep(interval)
    finally:
        close_redis()


if __name__ == "__main__":
    main()
