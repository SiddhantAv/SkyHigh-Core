"""HTTP: health and readiness."""

from fastapi.testclient import TestClient


def test_liveness(client: TestClient) -> None:
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "message" in body


def test_readiness(client: TestClient) -> None:
    r = client.get("/api/v1/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["data"]["database"] == "ok"
