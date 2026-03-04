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
    response = client.get("/health", headers={"x-request-id": "test-id-123"})
    assert response.headers["x-request-id"] == "test-id-123"
