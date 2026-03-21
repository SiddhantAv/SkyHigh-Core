# Architecture

SkyHigh Core is a **modular monolith**: one deployable Python process (FastAPI) with clear internal layers, backed by **PostgreSQL** and **Redis**, plus optional **separate worker processes** for background expiry.

## 1. High-level system context

```mermaid
flowchart LR
    subgraph clients[Clients]
        WEB[Web / mobile / kiosk]
    end
    subgraph skyhigh[SkyHigh deployment]
        API[FastAPI API]
        W[Expiry worker optional]
    end
    PG[(PostgreSQL)]
    RD[(Redis)]

    WEB --> API
    API --> PG
    API --> RD
    W --> PG
    W --> RD
    EXT[Optional weight HTTP service] -.-> API
```

- **PostgreSQL:** authoritative state for flights, passengers, seats, check-in sessions, idempotency keys.
- **Redis:** seat-map cache, rate-limit counters, optional seat locks, cache invalidation lists.
- **Worker:** batch seat expiry; does not replace DB locking in the API.

## 2. Application layering (hexagonal-style)

```mermaid
flowchart TB
    subgraph presentation[Presentation]
        R[FastAPI routers]
        S[Pydantic schemas]
        D[Dependencies: get_db, get_redis, services]
    end
    subgraph application[Application / domain services]
        SS[SeatService]
        CS[CheckinService]
    end
    subgraph persistence[Persistence]
        REP[Repositories]
        ORM[SQLAlchemy models]
    end
    subgraph infra[Infrastructure]
        RED[redis_client + cache]
        MID[Middleware: request id, rate limit]
    end

    R --> D
    D --> SS
    D --> CS
    SS --> REP
    SS --> RED
    CS --> REP
    REP --> ORM
    R --> MID
```

**Dependency rule:** routers depend on services and schemas; services depend on repositories and infrastructure ports; repositories depend on ORM/session. This keeps HTTP concerns separate from business rules.

## 3. Request path through the API

```mermaid
flowchart TD
    REQ[HTTP request] --> MW1[RequestIdMiddleware]
    MW1 --> MW2[RateLimitMiddleware]
    MW2 --> RT[Matched route]
    RT --> DEP[Inject Session + Redis + Service]
    DEP --> H[Route handler]
    H --> SVC[Service method]
    SVC --> DB[(PostgreSQL)]
    SVC --> RDX[(Redis)]
    H --> RES[JSON response]
    EX[Domain exception] --> EH[Exception handler]
    EH --> ERR[Structured JSON error]
```

- **Rate limiting** applies to `/api/v1/*` except health routes when enabled; Redis failures **fail open** (request continues, warning logged).
- **Exception handlers** in `main.py` map domain exceptions to **404 / 409 / 429 / 502** with a stable `error` code and `message`.

## 4. Concurrency model (seats)

```mermaid
flowchart LR
    subgraph api_tx[API transaction]
        L[SELECT seat FOR UPDATE]
        U[UPDATE seat row]
    end
    subgraph optional[Optional]
        RL[Redis lock per seat_id]
    end
    RL -.-> L
    L --> U
```

- **Primary mutex:** PostgreSQL row lock on the seat during hold/confirm.
- **Secondary:** optional Redis lock to serialize entrants before hitting the DB (configurable).

## 5. Caching strategy

| Data | Key pattern | Invalidation |
|------|-------------|--------------|
| Seat map per flight | Configured via cache helper (e.g. `seat_map:{flight_id}`) | After hold/confirm and after batch expiry updates |

On cache miss or Redis error during read, the service falls back to **database** for the seat list.

## 6. Deployment topology (Docker Compose)

The repository includes a **reference** Compose stack:

- **`api`** — Uvicorn-served FastAPI app, depends on healthy Postgres + Redis.
- **`expiry-worker`** — runs `python -m skyhigh.workers.expiry_loop` with the same DB/Redis URLs.
- **`postgres`**, **`redis`** — data stores.

Production would typically add: TLS termination, secrets management, migration job or init container, metrics, and backups—outside the scope of this minimal compose file.

## 7. Configuration

All environment-driven behavior is centralized in `skyhigh.config.Settings` (loaded from `.env` and the environment). See [README.md](README.md) for the variable table.

## 8. Related documents

| Document | Focus |
|----------|--------|
| [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) | Folders and modules |
| [WORKFLOW_DESIGN.md](WORKFLOW_DESIGN.md) | Flows and schema narrative |
| [API-SPECIFICATION.md](API-SPECIFICATION.md) | HTTP endpoints |
| [PRD.md](PRD.md) | Product goals and NFRs |
