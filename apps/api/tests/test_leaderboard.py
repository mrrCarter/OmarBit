"""Tests for leaderboard and replay API endpoints."""

import os

os.environ["SKIP_DB"] = "true"
os.environ.setdefault("NEXTAUTH_SECRET", os.urandom(32).hex())

from fastapi.testclient import TestClient

from main import app

client = TestClient(app, raise_server_exceptions=False)


def test_leaderboard_endpoint_exists():
    response = client.get("/api/v1/leaderboard")
    assert response.status_code not in (404, 405)


def test_replay_endpoint_exists():
    response = client.get("/api/v1/matches/00000000-0000-0000-0000-000000000001/replay")
    assert response.status_code not in (404, 405)


def test_replay_invalid_uuid():
    response = client.get("/api/v1/matches/not-a-uuid/replay")
    assert response.status_code == 400
