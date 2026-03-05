import os

os.environ["SKIP_DB"] = "true"

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_health_includes_request_id():
    response = client.get("/health")
    assert "x-request-id" in response.headers


def test_custom_request_id_preserved():
    valid_uuid = "12345678-1234-1234-1234-123456789abc"
    response = client.get("/health", headers={"x-request-id": valid_uuid})
    assert response.headers["x-request-id"] == valid_uuid


def test_invalid_request_id_replaced_with_uuid():
    response = client.get("/health", headers={"x-request-id": "not-a-uuid"})
    rid = response.headers["x-request-id"]
    # Should be a valid UUID, not the raw string
    assert rid != "not-a-uuid"
    assert len(rid) == 36
