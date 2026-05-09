# MEDI-IOT-EyeCare/tests/test_e2e_week4_full_flow.py
"""
Week 4 — 당뇨 환자 안과 검진 전체 E2E (VISION + RAG + CONSENSUS + 대시보드)

환경 변수 `RUN_WEEK4_E2E=1` 일 때만 실행 (LLM·시간 다수 소비).

  docker compose -f docker-compose.dev.yml exec -e RUN_WEEK4_E2E=1 medi-iot-api \\
    pytest tests/test_e2e_week4_full_flow.py -v -s --tb=short
"""
from __future__ import annotations

import io
import os
import sys
from datetime import date

import httpx
import pytest

sys.path.insert(0, "/app")
sys.path.insert(0, "/app/shared-libraries")

BASE_URL = "http://localhost:8000"
API_V1 = f"{BASE_URL}/api/v1"
TIMEOUT = httpx.Timeout(420.0)

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_WEEK4_E2E", "").lower() not in {"1", "true", "yes"},
    reason="RUN_WEEK4_E2E=1 일 때만 전체 LLM E2E 실행",
)


def _make_test_jpeg(size_kb: int = 12) -> bytes:
    return (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\x00\x00"
        + b"\x00" * max(0, size_kb * 1024 - 20)
        + b"\xff\xd9"
    )


@pytest.fixture
def patient_p999001() -> dict:
    """고정 코드 P999001 — 이미 있으면 조회로 id 확보."""
    code = "P999001"
    c = httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)
    r = c.post(
        f"{API_V1}/patients/",
        json={
            "patient_code": code,
            "name": "E2E테스트",
            "date_of_birth": "1970-01-01",
            "gender": "male",
            "primary_diagnosis_code": "H36.0",
            "notes": "Week4 E2E 당뇨망막병증 시나리오",
        },
    )
    if r.status_code == 201:
        return r.json()
    if r.status_code == 409:
        g = c.get(f"{API_V1}/patients/{code}")
        assert g.status_code == 200, g.text
        return g.json()
    raise AssertionError(f"환자 등록 실패: {r.status_code} {r.text}")


class TestWeek4DiabeticFullFlow:
    def test_full_flow_register_upload_ai_history_dashboard(self, patient_p999001):
        pid = patient_p999001["id"]
        code = patient_p999001["patient_code"]
        assert code == "P999001"

        c = httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)

        ex = c.post(
            f"{API_V1}/diagnosis/exam",
            json={
                "patient_id": pid,
                "exam_type": "fundus",
                "exam_date": str(date.today()),
                "icd_code": "H36.0",
                "iop_left": 16.0,
                "iop_right": 15.5,
                "visual_acuity_left": "0.6",
                "visual_acuity_right": "0.5",
                "raw_findings": (
                    "당뇨병성 망막병증 의심: 황반 주변 다발성 점상출혈, "
                    "경성삼출물, 미세동맥류."
                ),
            },
        )
        assert ex.status_code == 201, ex.text
        exam_id = ex.json()["id"]

        up = c.post(
            f"{API_V1}/images/upload",
            files={"file": ("e2e_fundus.jpg", io.BytesIO(_make_test_jpeg()), "image/jpeg")},
            data={
                "patient_id": pid,
                "image_type": "fundus",
                "exam_id": exam_id,
                "auto_analyze": "true",
            },
        )
        assert up.status_code == 201, up.text

        viz = "\n[VISION 이미지 분석 요약]"
        ana = up.json()
        if ana.get("analyzed"):
            ar = c.get(f"{API_V1}/images/{ana['id']}/analysis")
            if ar.status_code == 200 and ar.json().get("raw_analysis"):
                viz += "\n" + str(ar.json().get("raw_analysis"))[:600]

        dx = c.post(
            f"{API_V1}/diagnosis/ai-analyze",
            json={
                "exam_id": exam_id,
                "strategy": "consensus",
                "additional_context": "HbA1c 8%, 인슐린 치료 중." + viz,
            },
        )
        assert dx.status_code == 201, dx.text
        dbody = dx.json()
        assert dbody.get("diagnosis_code")
        assert "report" in dbody

        hist = c.get(f"{API_V1}/patients/{code}/history")
        assert hist.status_code == 200
        assert hist.json().get("patient_code") == code

        alerts = c.get(f"{API_V1}/dashboard/alerts")
        assert alerts.status_code == 200
        bod = alerts.json()
        assert "urgent_tracking" in bod
        assert "ontology_validator_warnings" in bod

        stats = c.get(f"{API_V1}/dashboard/stats")
        assert stats.status_code == 200

        llm = c.get(f"{API_V1}/dashboard/llm-usage")
        assert llm.status_code == 200
        assert llm.json().get("calls_today", 0) >= 0
