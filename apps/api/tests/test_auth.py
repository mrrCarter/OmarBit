import os

os.environ["SKIP_DB"] = "true"
os.environ.setdefault("NEXTAUTH_SECRET", os.urandom(32).hex())

from fastapi.testclient import TestClient
from jose import jwt

from main import app

# raise_server_exceptions=False: some endpoints touch DB after auth passes.
client = TestClient(app, raise_server_exceptions=False)

_TEST_SECRET = os.environ["NEXTAUTH_SECRET"]


def _make_token(payload: dict) -> str:
    return jwt.encode(payload, _TEST_SECRET, algorithm="HS256")


def test_missing_auth_header_returns_401():
    response = client.get("/api/v1/ai-profiles/me")
    assert response.status_code == 401
    body = response.json()
    assert body["detail"]["error"]["code"] == "UNAUTHORIZED"
    assert "requestId" in body["detail"]


def test_invalid_token_returns_401():
    response = client.get(
        "/api/v1/ai-profiles/me",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert response.status_code == 401


def test_token_missing_claims_returns_401():
    token = _make_token({"sub": "123"})
    response = client.get(
        "/api/v1/ai-profiles/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["detail"]["error"]["code"] == "UNAUTHORIZED"


def test_valid_token_passes_auth():
    token = _make_token({
        "github_id": "12345",
        "username": "testuser",
        "user_id": "00000000-0000-0000-0000-000000000000",
    })
    response = client.get(
        "/api/v1/ai-profiles/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    # Auth passes (not 401). Endpoint returns 500 because DB is not available.
    assert response.status_code != 401
