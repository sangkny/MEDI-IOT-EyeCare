"""MEDI 임상 연구 + 의사 검토 라우트 테스트 (Phase 2 → D 트랙).

테스트 철학 (Mock 0):
    - LLM/네트워크 Mock 절대 금지
    - 인증/입력 검증/Quota/RBAC/DB 영속화 검증은 LM Studio 없이도 가능
    - VISION 분석 사전 상태는 **DB 직접 시드** (LLM Mock 이 아닌 state 조작, 허용 패턴)

전략:
    실제 dev 서버 (localhost:8000) 에 sync ``httpx.Client`` 로 HTTP 호출 →
    ``BaseHTTPMiddleware`` + asyncpg 의 이벤트 루프 충돌 회피. DB 시드는
    매번 새 ``NullPool`` async engine 으로 격리해 loop 충돌 방지.

LM Studio 없이 본 스위트는 모두 통과 (LLM 호출 경로 미진입).
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import date, datetime, timezone

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from config import get_settings
from models.medical import (
    Diagnosis,
    DiagnosisSeverityEnum,
    EyeExam,
    EyeImage,
    ExamTypeEnum,
    ImageTypeEnum,
    Patient,
    ReportStatusEnum,
)


BASE = "http://localhost:8000"


def _async_db_url() -> str:
    """``DATABASE_URL`` 환경변수가 동기 (postgresql://) 로 덮여있어도 asyncpg 보장."""
    url = get_settings().database_url
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


@pytest.fixture(scope="module")
def client() -> httpx.Client:
    with httpx.Client(base_url=BASE, timeout=30.0) as c:
        yield c


def _token(client: httpx.Client, username: str, password: str) -> str:
    r = client.post(
        "/api/v1/auth/token",
        data={"username": username, "password": password},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _headers(client: httpx.Client, role: str = "doctor") -> dict[str, str]:
    creds = {
        "admin": ("admin", "admin123"),
        "doctor": ("doctor", "doc123"),
        "staff": ("staff", "staff123"),
    }
    u, p = creds[role]
    return {"Authorization": f"Bearer {_token(client, u, p)}"}


def _seed_patient_image(
    patient_code: str | None = None, *, analyzed: bool = True
) -> tuple[str, str, str]:
    """Patient + EyeExam + EyeImage 를 동기적으로 시드. NullPool 임시 engine 사용.

    매 호출마다 fresh engine 을 만들고 ``dispose()`` 해 event loop 충돌 방지.
    반환: ``(patient_id, exam_id, image_id)``.
    """
    pcode = patient_code or f"D{uuid.uuid4().hex[:6].upper()}"

    async def _do() -> tuple[str, str, str]:
        url = _async_db_url()
        eng = create_async_engine(url, poolclass=NullPool)
        SessionLocal = async_sessionmaker(eng, expire_on_commit=False)
        try:
            async with SessionLocal() as s:
                patient = Patient(
                    id=str(uuid.uuid4()),
                    patient_code=pcode,
                    date_of_birth=date(1960, 1, 1),
                )
                s.add(patient)
                await s.flush()

                exam = EyeExam(
                    id=str(uuid.uuid4()),
                    patient_id=patient.id,
                    exam_type=ExamTypeEnum.FUNDUS,
                    exam_date=date.today(),
                    iop_left=22.0, iop_right=18.0,
                    raw_findings="DR 의심, 좌안 미세동맥류",
                    report_status=ReportStatusEnum.PENDING,
                )
                s.add(exam)

                img = EyeImage(
                    id=str(uuid.uuid4()),
                    patient_id=patient.id,
                    exam_id=exam.id,
                    image_type=ImageTypeEnum.FUNDUS,
                    file_path=f"/tmp/test/{uuid.uuid4().hex}.jpg",
                    file_name="test_fundus.jpg",
                    file_size=1024,
                    mime_type="image/jpeg",
                    analyzed=analyzed,
                    analysis_icd_code="H36.0" if analyzed else None,
                    analysis_severity="moderate" if analyzed else None,
                    analysis_result=json.dumps({
                        "condition": "diabetic_retinopathy",
                        "condition_kr": "당뇨망막병증",
                        "icd10_code": "H36.0",
                        "severity": "moderate",
                        "confidence": 0.82,
                        "brief_summary": "비증식성 당뇨망막병증 — 의사 검토 필요.",
                        "ontology_passed": True,
                        "model_used": "google/gemma-4-26b-a4b",
                    }, ensure_ascii=False) if analyzed else None,
                    analyzed_at=datetime.now(timezone.utc) if analyzed else None,
                )
                s.add(img)
                await s.commit()
                return patient.id, exam.id, img.id
        finally:
            await eng.dispose()

    return asyncio.run(_do())


def _fetch_diagnosis(diagnosis_id: str) -> Diagnosis | None:
    async def _do() -> Diagnosis | None:
        url = _async_db_url()
        eng = create_async_engine(url, poolclass=NullPool)
        SessionLocal = async_sessionmaker(eng, expire_on_commit=False)
        try:
            async with SessionLocal() as s:
                return await s.get(Diagnosis, diagnosis_id)
        finally:
            await eng.dispose()
    return asyncio.run(_do())


# ── 1. Studies 목록 + Messidor-2 시드 ─────────────────────────


def test_clinical_studies_no_auth_401(client: httpx.Client) -> None:
    r = client.get("/api/v1/clinical/studies")
    assert r.status_code == 401


def test_clinical_studies_list_contains_messidor2_seed(
    client: httpx.Client,
) -> None:
    r = client.get("/api/v1/clinical/studies", headers=_headers(client))
    assert r.status_code == 200, r.text
    body = r.json()
    codes = {s["code"] for s in body["studies"]}
    assert "messidor-2" in codes
    msd = next(s for s in body["studies"] if s["code"] == "messidor-2")
    assert msd["image_count_total"] == 1748
    assert msd["license"] == "ADCIS Free Research Use"
    assert msd["status"] == "draft"


def test_clinical_study_detail_404_for_unknown(client: httpx.Client) -> None:
    r = client.get(
        f"/api/v1/clinical/studies/{uuid.uuid4()}",
        headers=_headers(client),
    )
    assert r.status_code == 404


# ── 2. Memberships ────────────────────────────────────────


def test_membership_create_doctor_ok(client: httpx.Client) -> None:
    _patient_id, _exam_id, img_id = _seed_patient_image()

    rl = client.get("/api/v1/clinical/studies", headers=_headers(client))
    msd = next(s for s in rl.json()["studies"] if s["code"] == "messidor-2")
    study_id = msd["id"]

    r = client.post(
        f"/api/v1/clinical/studies/{study_id}/memberships",
        json={
            "image_id": img_id,
            "external_id": "IM000312",
            "ground_truth_icd": "H36.0",
            "ground_truth_severity": "moderate",
        },
        headers=_headers(client, "doctor"),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["study_id"] == study_id
    assert body["image_id"] == img_id
    assert body["external_id"] == "IM000312"


def test_membership_unknown_image_404(client: httpx.Client) -> None:
    rl = client.get("/api/v1/clinical/studies", headers=_headers(client))
    study_id = next(
        s for s in rl.json()["studies"] if s["code"] == "messidor-2"
    )["id"]
    r = client.post(
        f"/api/v1/clinical/studies/{study_id}/memberships",
        json={"image_id": str(uuid.uuid4())},
        headers=_headers(client, "doctor"),
    )
    assert r.status_code == 404


# ── 3. Diagnosis Promotion ──────────────────────────────────


def test_promote_unanalyzed_image_returns_400(client: httpx.Client) -> None:
    _p, exam_id, img_id = _seed_patient_image(analyzed=False)
    r = client.post(
        "/api/v1/clinical/diagnoses/promote",
        json={"image_id": img_id, "exam_id": exam_id},
        headers=_headers(client, "doctor"),
    )
    assert r.status_code == 400


def test_promote_creates_diagnosis_and_review(client: httpx.Client) -> None:
    _p, exam_id, img_id = _seed_patient_image()
    r = client.post(
        "/api/v1/clinical/diagnoses/promote",
        json={
            "image_id": img_id,
            "exam_id": exam_id,
            "treatment_plan": "황반 OCT 후속 + 안과 전문의 검진 4주 내",
        },
        headers=_headers(client, "doctor"),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["diagnosis_code"] == "H36.0"
    assert body["severity"] == "moderate"
    assert body["review_status"] == "pending_review"

    diag = _fetch_diagnosis(body["diagnosis_id"])
    assert diag is not None
    assert diag.exam_id == exam_id
    assert diag.diagnosis_code == "H36.0"
    assert diag.severity == DiagnosisSeverityEnum.MODERATE


def test_promote_exam_patient_mismatch_returns_400(client: httpx.Client) -> None:
    _p1, exam_id_1, _img_1 = _seed_patient_image()
    _p2, _exam_id_2, img_id_2 = _seed_patient_image()
    r = client.post(
        "/api/v1/clinical/diagnoses/promote",
        json={"image_id": img_id_2, "exam_id": exam_id_1},
        headers=_headers(client, "doctor"),
    )
    assert r.status_code == 400


# ── 4. Review Queue + 결정 ─────────────────────────────────


def test_review_single_get_returns_review(client: httpx.Client) -> None:
    """E R3-Day 2 — 새 단건 조회 라우트 (모바일 리뷰 상세 화면용)."""
    _p, exam_id, img_id = _seed_patient_image()
    promote = client.post(
        "/api/v1/clinical/diagnoses/promote",
        json={"image_id": img_id, "exam_id": exam_id},
        headers=_headers(client, "doctor"),
    )
    review_id = promote.json()["review_id"]

    r = client.get(
        f"/api/v1/clinical/reviews/{review_id}",
        headers=_headers(client),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == review_id
    assert body["status"] == "pending_review"
    assert "diagnosis_id" in body


def test_review_single_get_404_for_unknown(client: httpx.Client) -> None:
    r = client.get(
        f"/api/v1/clinical/reviews/{uuid.uuid4()}",
        headers=_headers(client),
    )
    assert r.status_code == 404


def test_review_queue_lists_pending(client: httpx.Client) -> None:
    _p, exam_id, img_id = _seed_patient_image()
    promote = client.post(
        "/api/v1/clinical/diagnoses/promote",
        json={"image_id": img_id, "exam_id": exam_id},
        headers=_headers(client, "doctor"),
    )
    review_id = promote.json()["review_id"]

    q = client.get(
        "/api/v1/clinical/reviews?status=pending_review&limit=200",
        headers=_headers(client),
    )
    assert q.status_code == 200
    ids = {r["id"] for r in q.json()["reviews"]}
    assert review_id in ids


def test_review_decide_approved_by_doctor(client: httpx.Client) -> None:
    _p, exam_id, img_id = _seed_patient_image()
    promote = client.post(
        "/api/v1/clinical/diagnoses/promote",
        json={"image_id": img_id, "exam_id": exam_id},
        headers=_headers(client, "doctor"),
    ).json()
    review_id = promote["review_id"]

    r = client.post(
        f"/api/v1/clinical/reviews/{review_id}/decide",
        json={
            "status": "approved",
            "review_notes": "AI 추정 동의. 안과 전문의 4주 후 재검 권장.",
        },
        headers=_headers(client, "doctor"),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "approved"
    assert body["reviewed_by"] == "doctor"
    assert body["review_notes"] is not None


def test_review_decide_already_decided_returns_409(client: httpx.Client) -> None:
    _p, exam_id, img_id = _seed_patient_image()
    promote = client.post(
        "/api/v1/clinical/diagnoses/promote",
        json={"image_id": img_id, "exam_id": exam_id},
        headers=_headers(client, "doctor"),
    ).json()
    review_id = promote["review_id"]

    client.post(
        f"/api/v1/clinical/reviews/{review_id}/decide",
        json={"status": "rejected", "review_notes": "재검 필요."},
        headers=_headers(client, "doctor"),
    )
    r2 = client.post(
        f"/api/v1/clinical/reviews/{review_id}/decide",
        json={"status": "approved"},
        headers=_headers(client, "doctor"),
    )
    assert r2.status_code == 409


def test_review_decide_staff_forbidden_403(client: httpx.Client) -> None:
    fake_id = str(uuid.uuid4())
    r = client.post(
        f"/api/v1/clinical/reviews/{fake_id}/decide",
        json={"status": "approved"},
        headers=_headers(client, "staff"),
    )
    assert r.status_code == 403


# ── 5. 입력 검증 ────────────────────────────────────────────


def test_review_decide_invalid_status_422(client: httpx.Client) -> None:
    r = client.post(
        f"/api/v1/clinical/reviews/{uuid.uuid4()}/decide",
        json={"status": "unknown"},
        headers=_headers(client, "doctor"),
    )
    assert r.status_code == 422
