"""Week 7 — JWT 로그인·RBAC 스모크 (DB·LLM 미사용)."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.requires_db]

from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client_api() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_auth_token_admin(client_api: TestClient) -> None:
    r = client_api.post(
        "/api/v1/auth/token",
        data={"username": "admin", "password": "admin123"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("token_type") == "bearer"
    assert "access_token" in body


def test_auth_token_invalid_password(client_api: TestClient) -> None:
    r = client_api.post(
        "/api/v1/auth/token",
        data={"username": "admin", "password": "wrong"},
    )
    assert r.status_code == 401


def test_dashboard_stats_without_token_401(client_api: TestClient) -> None:
    r = client_api.get("/api/v1/dashboard/stats")
    assert r.status_code == 401


def test_dashboard_stats_doctor_forbidden_403(client_api: TestClient) -> None:
    t = client_api.post(
        "/api/v1/auth/token",
        data={"username": "doctor", "password": "doc123"},
    ).json()["access_token"]
    r = client_api.get(
        "/api/v1/dashboard/stats",
        headers={"Authorization": f"Bearer {t}"},
    )
    assert r.status_code == 403


def test_dashboard_stats_admin_ok(client_api: TestClient) -> None:
    t = client_api.post(
        "/api/v1/auth/token",
        data={"username": "admin", "password": "admin123"},
    ).json()["access_token"]
    r = client_api.get(
        "/api/v1/dashboard/stats",
        headers={"Authorization": f"Bearer {t}"},
    )
    assert r.status_code == 200
    assert "exams_today" in r.json()


def test_oauth_google_mock_and_refresh(client_api: TestClient) -> None:
    r = client_api.post(
        "/api/v1/auth/oauth/google",
        json={"code": "mock_hello"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "refresh_token" in body
    ref = client_api.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": body["refresh_token"]},
    )
    assert ref.status_code == 200
    assert ref.json().get("token_type") == "bearer"
