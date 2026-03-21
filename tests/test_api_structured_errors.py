"""HTTP: structured error body shape for domain failures."""

from fastapi.testclient import TestClient


def test_hold_unknown_seat_returns_structured_error(client: TestClient) -> None:
    r = client.post(
        "/api/v1/seats/999999/hold",
        json={"passenger_id": 1, "idempotency_key": "e2e-hold-missing"},
    )
    assert r.status_code == 404
    body = r.json()
    assert body["error"] == "SeatNotFound"
    assert "message" in body
    assert body["details"]["seat_id"] == 999999


def test_payment_unknown_session(client: TestClient) -> None:
    r = client.post(
        "/api/v1/checkin/payment",
        json={"checkin_session_id": 424242},
    )
    assert r.status_code == 404
    body = r.json()
    assert body["error"] == "CheckInSessionNotFound"
    assert body["details"]["checkin_session_id"] == 424242
