"""Tests for tournament API endpoint."""

import os

os.environ["SKIP_DB"] = "true"
os.environ.setdefault("NEXTAUTH_SECRET", os.urandom(32).hex())

from fastapi.testclient import TestClient
from jose import jwt

from main import app

client = TestClient(app, raise_server_exceptions=False)

_TEST_SECRET = os.environ["NEXTAUTH_SECRET"]


def _make_token() -> str:
    return jwt.encode(
        {"github_id": "12345", "username": "testuser", "user_id": "00000000-0000-0000-0000-000000000000"},
        _TEST_SECRET,
        algorithm="HS256",
    )


def test_schedule_tournament_requires_auth():
    response = client.post("/api/v1/tournaments/schedule")
    assert response.status_code == 401


def test_schedule_tournament_endpoint_exists():
    token = _make_token()
    response = client.post(
        "/api/v1/tournaments/schedule",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code not in (404, 405)
