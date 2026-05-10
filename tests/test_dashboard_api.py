# MEDI-IOT-EyeCare/tests/test_dashboard_api.py
"""
Week 4 — 대시보드 API 스모크 테스트 (LLM 미사용)

실행:
  docker compose -f docker-compose.dev.yml exec medi-iot-api \\
    pytest tests/test_dashboard_api.py -v --tb=short
"""
from __future__ import annotations

import sys

import httpx

sys.path.insert(0, "/app")
sys.path.insert(0, "/app/shared-libraries")

BASE_URL = "http://localhost:8000"
API_V1 = f"{BASE_URL}/api/v1"
TIMEOUT = httpx.Timeout(30.0)


def _admin_headers() -> dict[str, str]:
    r = httpx.post(
        f"{API_V1}/auth/token",
        data={"username": "admin", "password": "admin123"},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


class TestDashboardAPI:
    """GET /api/v1/dashboard/* 응답 스키마 스모크 검증."""

    def test_dashboard_stats_structure(self):
        r = httpx.get(
            f"{API_V1}/dashboard/stats",
            timeout=TIMEOUT,
            headers=_admin_headers(),
        )
        assert r.status_code == 200
        body = r.json()
        assert "exams_today" in body
        assert "new_patients_today" in body
        assert isinstance(body["diagnosis_buckets"], list)
        agr = body["ai_icd_agreement_vs_exam"]
        assert "compared_pairs" in agr
        assert "matched_pairs" in agr

    def test_dashboard_alerts_structure(self):
        r = httpx.get(
            f"{API_V1}/dashboard/alerts",
            timeout=TIMEOUT,
            headers=_admin_headers(),
        )
        assert r.status_code == 200
        body = r.json()
        assert "generated_at" in body
        assert isinstance(body["urgent_tracking"], list)
        assert isinstance(body["ontology_validator_warnings"], list)

    def test_dashboard_llm_usage_structure(self):
        r = httpx.get(
            f"{API_V1}/dashboard/llm-usage",
            timeout=TIMEOUT,
            headers=_admin_headers(),
        )
        assert r.status_code == 200
        body = r.json()
        assert "calls_today" in body
        assert "total_tokens_estimated" in body
        assert isinstance(body["by_provider"], list)
