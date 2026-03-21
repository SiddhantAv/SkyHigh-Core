# Product Requirements Document (PRD) — SkyHigh Core

## 1. Problem statement

Airlines and digital check-in products must manage **finite seat inventory** under **concurrent users**: many passengers may attempt to select the same seat at the same time, holds must **expire fairly**, and check-in must enforce **baggage rules** without corrupting state. Ad-hoc implementations often produce double bookings, stale UI, or inconsistent baggage handling.

**SkyHigh Core** is a backend API that provides **concurrency-safe seat lifecycle management** (hold → confirm), **cached seat maps** for scale, and a **check-in session** flow with optional **external baggage verification** and a **simulated extra-baggage payment** path.

## 2. Goals the system must achieve

| Goal | Description |
|------|-------------|
| **No overlapping seat assignments** | At most one successful **HELD** or **CONFIRMED** outcome per seat for conflicting operations; database row locking and transactional updates prevent two passengers from holding the same seat. |
| **Predictable hold expiry** | Time-bounded holds (`held_until`); expired **HELD** seats return to **AVAILABLE** via lazy cleanup on reads and batch workers using PostgreSQL `SKIP LOCKED`. |
| **Fast seat-map reads** | Flight seat lists are served from **Redis** when valid; cache invalidation on seat changes keeps correctness while improving read latency. |
| **Reliable retries** | **Idempotency keys** for hold and confirm so network retries do not create duplicate side effects or mismatched seats. |
| **Check-in with baggage validation** | Check-in starts only for **CONFIRMED** seats owned by the passenger; baggage weight is compared to a configurable limit (default **25 kg**), with optional verification via an external **weight service**. |
| **Over-limit path** | When baggage exceeds the limit, the session enters **WAITING_FOR_PAYMENT** until **simulated payment** completes, then check-in can finish. |
| **Operability** | Health and readiness endpoints support orchestration; rate limiting and optional Redis seat locks reduce abuse and hot-seat contention. |

## 3. Key users

| User / actor | Interaction |
|--------------|-------------|
| **Passenger-facing client** (web / mobile / kiosk) | Calls APIs to view seat maps, hold and confirm seats, and run the check-in flow (start → complete or payment). |
| **Airline operations / support** | Indirectly: consumes structured errors, session states, and logs for troubleshooting (no separate admin UI in this codebase). |
| **Platform / SRE** | Deploys API and workers, configures PostgreSQL and Redis, runs migrations, monitors health/readiness and rate limits. |
| **Integrations** | Optional **weight verification service** (HTTP POST) when `WEIGHT_SERVICE_URL` is set. |

## 4. Non-functional requirements (NFRs)

### 4.1 Performance & scalability

- Seat map responses should tolerate high read volume via **Redis caching** (TTL configurable).
- Seat expiry processing uses **batched** updates to avoid long table locks.
- Optional **per-IP rate limiting** (Redis fixed window) and **per-passenger hold burst limits** protect the API.

### 4.2 Reliability & correctness

- **PostgreSQL** is the **source of truth** for seat and check-in state; Redis is cache and coordination (locks, counters), not authoritative.
- **Fail-open** behavior where appropriate: if Redis errors during rate limit checks, requests proceed (logged).
- **Idempotency** for hold/confirm reduces duplicate operations under retries.

### 4.3 Security & compliance (baseline)

- Structured error responses avoid leaking internal stack traces to clients (handled exceptions mapped to HTTP status and JSON body).
- Configuration via environment variables; **no secrets in repository code**.
- Trust boundaries: `X-Forwarded-For` used only for rate-limit client IP derivation when present (deploy behind a trusted proxy or adjust as needed).

### 4.4 Observability

- Request correlation via **request ID** middleware.
- Logging level configurable (`LOG_LEVEL`).

### 4.5 Maintainability

- Clear layering: API → services → repositories → models.
- Migrations via **Alembic** against SQLAlchemy `Base.metadata`.
- Automated **pytest** suite (including SQLite for fast CI-style runs).

### 4.6 Compatibility

- **Python 3.11+** (see `pyproject.toml`).
- Production database target: **PostgreSQL** (batch seat expiry uses PostgreSQL-specific SQL).

---

*This PRD reflects the behavior implemented in this repository as of the current codebase.*
