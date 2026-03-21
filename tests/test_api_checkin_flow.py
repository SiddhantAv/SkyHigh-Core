"""HTTP: baggage check-in + simulated payment."""

from fastapi.testclient import TestClient


def test_start_checkin_within_limit_then_complete(
    client: TestClient,
    checkin_world: dict[str, int],
) -> None:
    r1 = client.post(
        "/api/v1/checkin/start",
        json={
            "passenger_id": checkin_world["passenger_id"],
            "seat_id": checkin_world["seat_id"],
            "baggage_weight": 12.5,
        },
    )
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1["status"] == "IN_PROGRESS"

    r2 = client.post(
        "/api/v1/checkin/complete",
        json={
            "passenger_id": checkin_world["passenger_id"],
            "seat_id": checkin_world["seat_id"],
        },
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "COMPLETED"


def test_start_checkin_overweight_then_pay(
    client: TestClient,
    checkin_world: dict[str, int],
) -> None:
    r1 = client.post(
        "/api/v1/checkin/start",
        json={
            "passenger_id": checkin_world["passenger_id"],
            "seat_id": checkin_world["seat_id"],
            "baggage_weight": 30.0,
        },
    )
    assert r1.status_code == 200
    sid = r1.json()["data"]["checkin_session_id"]
    r2 = client.post(
        "/api/v1/checkin/payment",
        json={"checkin_session_id": sid},
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "COMPLETED"
