"""API surface tests — boot the app in-process, no DB required.

Generating the OpenAPI schema forces FastAPI to validate every route signature
and response_model across all routers, so this catches contract breakage early.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

EXPECTED_ROUTES = {
    "/health",
    "/health/ready",
    "/api/agreements/upload",
    "/api/agreements/{agreement_id}/metadata",
    "/api/agreements/{agreement_id}/export",
    "/api/jobs/{job_id}",
    "/api/rates",
    "/api/rates/{rate_id}/provenance",
    "/api/review/jobs/{job_id}/tasks",
    "/api/review/tasks/{task_id}",
    "/api/review/jobs/{job_id}/approve",
    "/api/search",
    "/api/vendors",
}


def test_liveness():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_readiness_reports_db_status():
    # The probe actually checks the DB: 200+ready when reachable, 503 when not.
    # (Environment-agnostic — a DB may or may not be present in the test context.)
    r = client.get("/health/ready")
    assert r.status_code in (200, 503)
    assert "db" in r.json()


def test_openapi_generates_and_registers_all_routes():
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = set(r.json()["paths"].keys())
    missing = EXPECTED_ROUTES - paths
    assert not missing, f"missing routes: {missing}"
