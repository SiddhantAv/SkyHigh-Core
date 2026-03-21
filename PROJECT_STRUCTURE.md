# Project structure

This document describes the layout of the **SkyHigh** repository and the purpose of each major folder and module.

## Root directory

| Path | Purpose |
|------|---------|
| `src/skyhigh/` | Main Python package (installable via `pip install -e .`). |
| `tests/` | Pytest suite; `conftest.py` sets test `DATABASE_URL` and app overrides. |
| `alembic/` | Database migration scripts and `env.py` (reads `DATABASE_URL` from settings). |
| `alembic.ini` | Alembic configuration (`script_location`, logging). |
| `docker/` | `Dockerfile` and `docker-compose.yml` for API, PostgreSQL, Redis, and the expiry worker. |
| `scripts/` | Utility scripts (e.g. seat-map load testing). |
| `pyproject.toml` | Project metadata, dependencies, pytest/coverage options. |
| `requirements.txt` | Pinned dependencies (alternative to `pyproject.toml` installs). |
| `.env` / `.env.example` | Local environment variables (not committed if secrets present). |

## `src/skyhigh/` — application package

| Module / package | Purpose |
|------------------|---------|
| `main.py` | FastAPI app factory (`create_app`), lifespan (Redis pool init/close), global exception handlers, middleware registration. |
| `config.py` | `pydantic-settings` `Settings`: DB URL, Redis URL, hold TTL, rate limits, baggage limits, weight service URL, worker intervals. |
| `logging.py` | Application logging configuration. |
| `exceptions.py` | Domain exceptions mapped to HTTP responses (seat errors, check-in errors, idempotency mismatch, rate limit, weight service). |

### `api/`

HTTP layer only: routing, dependency injection, Pydantic request/response models.

| Path | Purpose |
|------|---------|
| `api/deps.py` | FastAPI dependencies: DB session, Redis client, `SeatService`, `CheckinService`. |
| `api/v1/router.py` | Aggregates v1 routers under `/api/v1`. |
| `api/v1/checkin.py` | Seat hold and confirm endpoints. |
| `api/v1/flights.py` | Flight seat map endpoint. |
| `api/v1/checkin_flow.py` | Check-in start, complete, and payment endpoints. |
| `api/v1/health.py` | Liveness and readiness probes. |
| `api/schemas/` | Pydantic models for API bodies and envelopes (`checkin`, `checkin_flow`, `flights`, `health`, `errors`). |

### `db/`

Persistence metadata and session management.

| Path | Purpose |
|------|---------|
| `db/base.py` | Declarative `Base` for SQLAlchemy models. |
| `db/session.py` | Engine, `SessionLocal`, `get_db` dependency generator. |
| `db/models/` | ORM entities: `Flight`, `Passenger`, `Seat`, `CheckInSession`, `IdempotencyKey`, and enums (`SeatStatus`, `CheckInStatus`, `PaymentStatus`). |

### `repositories/`

Data access and SQL-focused operations (queries, row locks, bulk updates).

| Module | Purpose |
|--------|---------|
| `seat_repository.py` | Seat CRUD-style access, `SELECT … FOR UPDATE`, seat map projection, lazy expiry, bulk / batch expiry (PostgreSQL CTE + `SKIP LOCKED`). |
| `idempotency_repository.py` | Idempotency key rows, `FOR UPDATE` serialization, cleanup by age. |
| `checkin_repository.py` | Check-in session persistence and lookups. |

### `services/`

Business use cases orchestrating repositories and infrastructure.

| Module | Purpose |
|--------|---------|
| `seat_service.py` | Hold / confirm seat with idempotency, optional Redis seat lock, passenger hold rate limit, seat map with cache read-through and invalidation. |
| `checkin_service.py` | Start check-in (baggage rules, optional weight service), complete check-in, simulated payment completion. |

### `infrastructure/`

Cross-cutting technical adapters.

| Module | Purpose |
|--------|---------|
| `redis_client.py` | Process-wide Redis connection pool: `init_redis`, `get_redis`, `close_redis`. |
| `cache.py` | Seat map Redis keys, get/set/invalidate helpers. |
| `seat_redis_lock.py` | Optional Redis lock around hot seat operations. |

### `observability/`

| Module | Purpose |
|--------|---------|
| `middleware.py` | Request ID middleware. |
| `rate_limit.py` | Per-IP fixed-window rate limiting middleware (Redis). |
| `context.py` | Request-scoped context helpers if used by logging/tracing. |

### `workers/`

Background jobs (run beside the API or as separate containers/processes).

| Module | Purpose |
|--------|---------|
| `expiry_worker.py` | `run_seat_expiry_job`: batched expiry of stale **HELD** seats + cache invalidation. |
| `expiry_loop.py` | Long-running loop calling the expiry job on an interval (`python -m skyhigh.workers.expiry_loop`). |
| `idempotency_cleanup_worker.py` | `run_idempotency_cleanup`: deletes old `idempotency_keys` rows (schedulable; no dedicated Compose service in-repo). |
| `__init__.py` | Re-exports public worker entrypoints. |

---

For runtime architecture and request flows, see [ARCHITECTURE.md](ARCHITECTURE.md) and [WORKFLOW_DESIGN.md](WORKFLOW_DESIGN.md).
