# API specification

Base URL prefix: **`/api/v1`**

Unless noted, requests and responses use **`application/json`**. Successful seat and check-in operations return an envelope with `status`, `message`, and `data` (see schemas below).

Interactive docs (when the app is running): **`/docs`** (Swagger UI), **`/redoc`**.

## Common error shape

Many error responses use:

```json
{
  "error": "StableCode",
  "message": "Human-readable explanation.",
  "details": { "optional": "context" }
}
```

`details` may be omitted. Exact `error` values correspond to exception types in `skyhigh.exceptions` (e.g. `SeatNotFound`, `SeatAlreadyHeld`).

---

## Health

### `GET /api/v1/health`

**Summary:** Liveness — process is up (no DB/Redis check).

**Response 200:** `HealthApiResponse`

| Field | Type | Notes |
|-------|------|--------|
| `status` | string | e.g. `"ok"` |
| `message` | string | |
| `data` | object or null | |

---

### `GET /api/v1/health/ready`

**Summary:** Readiness — executes `SELECT 1` on PostgreSQL and `PING` on Redis.

**Response 200:** `ReadyApiResponse`

| Field | Type | Notes |
|-------|------|--------|
| `status` | string | e.g. `"ready"` |
| `message` | string | |
| `data` | object | e.g. `{"database":"ok","redis":"ok"}` |

**Errors:** connection failures surface as **5xx** from unhandled DB/Redis errors.

---

## Flights — seat map

### `GET /api/v1/flights/{flight_id}/seats`

**Summary:** Returns all seats for a flight. Uses Redis cache when available; expired **HELD** seats for that flight may be cleared in PostgreSQL before the read.

**Path parameters**

| Name | Type | Description |
|------|------|-------------|
| `flight_id` | integer | Flight primary key |

**Response 200:** `SeatMapApiResponse`

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | e.g. `"success"` |
| `message` | string | |
| `data.flight_id` | integer | Same as path |
| `data.seats` | array | List of seat rows |

Each seat row:

| Field | Type | Description |
|-------|------|-------------|
| `seat_id` | integer | |
| `seat_number` | string | |
| `status` | string | `AVAILABLE`, `HELD`, or `CONFIRMED` |

---

## Seats — hold and confirm

### `POST /api/v1/seats/{seat_id}/hold`

**Summary:** Temporarily reserves a seat (default hold duration from `HOLD_DURATION_SECONDS`, e.g. 120). **Idempotent** per `idempotency_key` for the same seat.

**Path parameters**

| Name | Type |
|------|------|
| `seat_id` | integer |

**Request body:** `HoldSeatRequest`

| Field | Type | Constraints |
|-------|------|-------------|
| `passenger_id` | integer | ≥ 1 |
| `idempotency_key` | string | 1–512 chars |

**Response 200:** `HoldSeatApiResponse`

| Field | Type |
|-------|------|
| `status` | string | e.g. `"HELD"` |
| `message` | string |
| `data.seat_id` | integer |
| `data.held_until` | string (ISO 8601) or null |

**Errors**

| HTTP | Condition |
|------|-----------|
| 404 | Seat does not exist |
| 409 | Seat unavailable, already confirmed, hold expired, idempotency key reused for a different seat, etc. |
| 429 | Passenger hold rate limit exceeded (when enabled) |

---

### `POST /api/v1/seats/{seat_id}/confirm`

**Summary:** Converts an active **HELD** seat to **CONFIRMED** for the same passenger. **Idempotent** per `idempotency_key`.

**Path parameters**

| Name | Type |
|------|------|
| `seat_id` | integer |

**Request body:** `ConfirmSeatRequest`

| Field | Type | Constraints |
|-------|------|-------------|
| `passenger_id` | integer | ≥ 1 |
| `idempotency_key` | string | 1–512 chars |

**Response 200:** `ConfirmSeatApiResponse`

| Field | Type |
|-------|------|
| `status` | string | e.g. `"CONFIRMED"` |
| `message` | string |
| `data.seat_id` | integer |

**Errors**

| HTTP | Condition |
|------|-----------|
| 404 | Seat does not exist |
| 409 | Not held by passenger, hold expired, already confirmed, idempotency mismatch, etc. |

---

## Check-in

### `POST /api/v1/checkin/start`

**Summary:** Starts check-in for a **CONFIRMED** seat belonging to the passenger. Compares resolved baggage weight to `MAX_BAGGAGE_KG` (default 25).

**Request body:** `CheckinStartRequest`

| Field | Type | Constraints |
|-------|------|-------------|
| `passenger_id` | integer | ≥ 1 |
| `seat_id` | integer | ≥ 1 |
| `baggage_weight` | number | ≥ 0 (kg) |

**Response 200:** `CheckinStartResponse`

| Field | Type |
|-------|------|
| `status` | string | `IN_PROGRESS` or `WAITING_FOR_PAYMENT` (or `COMPLETED` if already completed — idempotent-style messaging) |
| `message` | string |
| `data.checkin_session_id` | integer |
| `data.baggage_weight` | number or null |

**Errors**

| HTTP | Condition |
|------|-----------|
| 409 | Seat not confirmed, wrong passenger, invalid state for start |

**Optional weight service:** if `WEIGHT_SERVICE_URL` is set, the service POSTs JSON `{"passenger_id", "declared_kg"}` and expects `{"verified_kg"}`. Failures map to **502** (`WeightServiceError`).

---

### `POST /api/v1/checkin/complete`

**Summary:** Completes check-in when the session is **IN_PROGRESS** (baggage already within limit).

**Request body:** `CheckinCompleteRequest`

| Field | Type |
|-------|------|
| `passenger_id` | integer |
| `seat_id` | integer |

**Response 200:** `CheckinCompleteResponse` — `status` typically `COMPLETED`; `data` includes `checkin_session_id` and `baggage_weight`.

**Errors**

| HTTP | Condition |
|------|-----------|
| 409 | Wrong state (e.g. still `WAITING_FOR_PAYMENT`), wrong passenger/seat |

---

### `POST /api/v1/checkin/payment`

**Summary:** Simulated payment: marks extra baggage as paid and completes check-in when status is **WAITING_FOR_PAYMENT**.

**Request body:** `PaymentRequest`

| Field | Type |
|-------|------|
| `checkin_session_id` | integer |

**Response 200:** `PaymentCompleteResponse`

| Field | Type |
|-------|------|
| `status` | string | e.g. `COMPLETED` |
| `message` | string |
| `data.checkin_session_id` | integer |

**Errors**

| HTTP | Condition |
|------|-----------|
| 404 | Session id not found |
| 409 | Session not in `WAITING_FOR_PAYMENT` |

---

## Rate limiting (when enabled)

For `/api/v1` routes (except health), the API may return:

**429 Too Many Requests** with header `Retry-After` (seconds).

Separate fixed windows apply to **GET** (and **HEAD**) vs **POST** traffic per client IP (see `RATE_LIMIT_*` settings).

---

## OpenAPI

The canonical machine-readable spec is served at **`/openapi.json`** when the application is running.
