"""OpenAPI document is generated."""

from fastapi.testclient import TestClient


def test_openapi_json(client: TestClient) -> None:
    r = client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    assert spec["info"]["title"] == "SkyHigh Core"
    paths = spec["paths"]
    assert "/api/v1/health" in paths
    assert "/api/v1/checkin/start" in paths
