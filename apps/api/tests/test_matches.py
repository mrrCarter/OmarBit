import os

os.environ["SKIP_DB"] = "true"
os.environ.setdefault("NEXTAUTH_SECRET", os.urandom(32).hex())

from fastapi.testclient import TestClient
from jose import jwt

from main import app

client = TestClient(app, raise_server_exceptions=False)

_TEST_SECRET = os.environ["NEXTAUTH_SECRET"]


def _make_token() -> str:
    import time
    return jwt.encode(
        {
            "github_id": "12345", "username": "testuser",
            "user_id": "00000000-0000-0000-0000-000000000000",
            "iss": "omarbit-web", "aud": "omarbit-api",
            "iat": int(time.time()), "exp": int(time.time()) + 3600,
        },
        _TEST_SECRET,
        algorithm="HS256",
    )


def test_start_match_requires_auth():
    response = client.post(
        "/api/v1/matches",
        json={"white_ai_id": "a", "black_ai_id": "b"},
        headers={"Idempotency-Key": "m-1"},
    )
    assert response.status_code == 401


def test_start_match_requires_idempotency_key():
    token = _make_token()
    response = client.post(
        "/api/v1/matches",
        json={"white_ai_id": "a", "black_ai_id": "b"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["error"]["code"] == "MISSING_IDEMPOTENCY_KEY"


def test_start_match_endpoint_exists():
    token = _make_token()
    response = client.post(
        "/api/v1/matches",
        json={
            "white_ai_id": "00000000-0000-0000-0000-000000000001",
            "black_ai_id": "00000000-0000-0000-0000-000000000002",
        },
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "m-2"},
    )
    assert response.status_code not in (404, 405)


def test_forfeit_match_requires_auth():
    response = client.post(
        "/api/v1/matches/fake-id/forfeit",
        json={"reason": "test"},
        headers={"Idempotency-Key": "f-1"},
    )
    assert response.status_code == 401


def test_forfeit_match_requires_idempotency_key():
    token = _make_token()
    response = client.post(
        "/api/v1/matches/fake-id/forfeit",
        json={"reason": "test"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400


def test_get_match_endpoint_exists():
    response = client.get("/api/v1/matches/fake-id")
    assert response.status_code not in (404, 405)


def test_sse_stream_endpoint_exists():
    response = client.get("/api/v1/stream/matches/fake-id")
    assert response.status_code not in (404, 405)
