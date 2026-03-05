import os

os.environ["SKIP_DB"] = "true"

from fastapi.testclient import TestClient

from main import app

# raise_server_exceptions=False: DB pool not available in test env,
# so DB-dependent endpoints return 500 instead of crashing the test runner.
client = TestClient(app, raise_server_exceptions=False)


def test_feature_flags_endpoint_exists():
    response = client.get("/api/v1/feature-flags")
    # Returns 500 (DB not available) but not 404/405 (endpoint exists)
    assert response.status_code not in (404, 405)


def test_admin_feature_flags_requires_auth():
    response = client.patch(
        "/api/v1/admin/feature-flags/test_flag",
        json={"enabled": True},
    )
    assert response.status_code == 401


def test_admin_feature_flags_endpoint_exists():
    response = client.patch(
        "/api/v1/admin/feature-flags/test_flag",
        json={"enabled": True},
    )
    assert response.status_code not in (404, 405)
