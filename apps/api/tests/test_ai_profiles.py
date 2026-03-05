import os

os.environ["SKIP_DB"] = "true"
os.environ.setdefault("NEXTAUTH_SECRET", os.urandom(32).hex())

from fastapi.testclient import TestClient
from jose import jwt

from main import app

# raise_server_exceptions=False: DB pool not available in test env.
client = TestClient(app, raise_server_exceptions=False)

_TEST_SECRET = os.environ["NEXTAUTH_SECRET"]


def _make_token() -> str:
    return jwt.encode(
        {"github_id": "12345", "username": "testuser", "user_id": "00000000-0000-0000-0000-000000000000"},
        _TEST_SECRET,
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


def test_patch_profile_requires_auth():
    response = client.patch(
        "/api/v1/ai-profiles/some-id",
        json={"display_name": "Updated"},
    )
    assert response.status_code == 401


def test_patch_profile_endpoint_exists():
    token = _make_token()
    response = client.patch(
        "/api/v1/ai-profiles/some-id",
        json={"display_name": "Updated"},
        headers={"Authorization": f"Bearer {token}"},
    )
    # Not 404 method-wise — might be 500 (no DB) or 404 (profile not found)
    assert response.status_code != 405


def test_patch_profile_validates_style():
    token = _make_token()
    response = client.patch(
        "/api/v1/ai-profiles/some-id",
        json={"style": "invalid_style"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


def test_delete_profile_requires_auth():
    response = client.delete("/api/v1/ai-profiles/some-id")
    assert response.status_code == 401


def test_delete_profile_endpoint_exists():
    token = _make_token()
    response = client.delete(
        "/api/v1/ai-profiles/some-id",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code != 405


def test_match_history_endpoint_exists():
    response = client.get("/api/v1/ai-profiles/some-id/matches")
    # Public endpoint — should not be 404/405 (route exists)
    assert response.status_code != 405


def test_match_history_accepts_pagination():
    response = client.get("/api/v1/ai-profiles/some-id/matches?limit=10&offset=5")
    assert response.status_code != 405
