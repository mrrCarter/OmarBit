import os

os.environ["SKIP_DB"] = "true"
os.environ["NEXTAUTH_SECRET"] = "test-secret-for-jwt"

from fastapi.testclient import TestClient
from jose import jwt

from main import app

# raise_server_exceptions=False: DB pool not available in test env.
client = TestClient(app, raise_server_exceptions=False)

SECRET = "test-secret-for-jwt"


def _make_token() -> str:
    return jwt.encode(
        {"github_id": "12345", "username": "testuser", "user_id": "00000000-0000-0000-0000-000000000000"},
        SECRET,
        algorithm="HS256",
    )


def test_create_ai_profile_requires_auth():
    response = client.post(
        "/api/v1/ai-profiles",
        json={"display_name": "TestAI", "provider": "claude", "api_key": "sk-test"},
        headers={"Idempotency-Key": "test-key-1"},
    )
    assert response.status_code == 401


def test_create_ai_profile_requires_idempotency_key():
    token = _make_token()
    response = client.post(
        "/api/v1/ai-profiles",
        json={"display_name": "TestAI", "provider": "claude", "api_key": "sk-test"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["error"]["code"] == "MISSING_IDEMPOTENCY_KEY"


def test_create_ai_profile_validates_provider():
    token = _make_token()
    response = client.post(
        "/api/v1/ai-profiles",
        json={"display_name": "TestAI", "provider": "invalid_provider", "api_key": "sk-test"},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "test-key-2"},
    )
    assert response.status_code == 422


def test_list_profiles_requires_auth():
    response = client.get("/api/v1/ai-profiles/me")
    assert response.status_code == 401


def test_create_ai_profile_endpoint_exists():
    token = _make_token()
    response = client.post(
        "/api/v1/ai-profiles",
        json={"display_name": "TestAI", "provider": "claude", "api_key": "sk-test"},
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "test-key-3"},
    )
    # Not 404/405 = endpoint exists. 500 = DB not available (expected).
    assert response.status_code not in (404, 405)
