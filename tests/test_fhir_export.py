"""FHIR R4 export API 테스트 (D R3 D4).

Mock 0 — DB 직접 시드, httpx 로 실 서버 호출. LLM/외부 FHIR 서버 없음.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone

import httpx
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.requires_db]
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
from services.fhir_export import FHIR_JSON

BASE = "http://localhost:8000"
FHIR_CT = "application/fhir+json"


def _async_db_url() -> str:
    url = get_settings().database_url
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://") :]
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
    }
    u, p = creds[role]
    return {"Authorization": f"Bearer {_token(client, u, p)}"}


def _seed_fhir_fixtures() -> tuple[str, str, str]:
    """patient_id, image_id, diagnosis_id."""

    async def _do() -> tuple[str, str, str]:
        eng = create_async_engine(_async_db_url(), poolclass=NullPool)
        SM = async_sessionmaker(eng, expire_on_commit=False)
        try:
            async with SM() as s:
                p = Patient(
                    id=str(uuid.uuid4()),
                    patient_code=f"FHIR-{uuid.uuid4().hex[:6].upper()}",
                    date_of_birth=date(1955, 6, 15),
                )
                s.add(p)
                await s.flush()

                exam = EyeExam(
                    id=str(uuid.uuid4()),
                    patient_id=p.id,
                    exam_type=ExamTypeEnum.FUNDUS,
                    exam_date=date.today(),
                    raw_findings="FHIR export test",
                    report_status=ReportStatusEnum.COMPLETED,
                )
                s.add(exam)
                await s.flush()

                analysis = {
                    "condition": "diabetic_retinopathy",
                    "condition_kr": "당뇨망막병증",
                    "icd10_code": "H36.0",
                    "severity": "moderate",
                    "confidence": 0.88,
                    "ontology_passed": True,
                    "model_used": "consensus(gemma,mistral)",
                }
                img = EyeImage(
                    id=str(uuid.uuid4()),
                    patient_id=p.id,
                    exam_id=exam.id,
                    image_type=ImageTypeEnum.FUNDUS,
                    file_path=f"/tmp/fhir/{uuid.uuid4().hex}.jpg",
                    file_name="fhir.jpg",
                    file_size=512,
                    mime_type="image/jpeg",
                    analyzed=True,
                    analyzed_at=datetime.now(timezone.utc),
                    analysis_icd_code="H36.0",
                    analysis_severity="moderate",
                    analysis_result=json.dumps(analysis, ensure_ascii=False),
                )
                s.add(img)

                diag = Diagnosis(
                    id=str(uuid.uuid4()),
                    exam_id=exam.id,
                    diagnosis_code="H36.0",
                    diagnosis_name="당뇨망막병증",
                    severity=DiagnosisSeverityEnum.MODERATE,
                    report="FHIR DiagnosticReport conclusion text.",
                    llm_model="consensus(gemma,mistral)",
                    ontology_passed=True,
                    confidence_score=0.88,
                )
                s.add(diag)
                await s.commit()
                return p.id, img.id, diag.id
        finally:
            await eng.dispose()

    import asyncio

    return asyncio.run(_do())


def test_fhir_patient_requires_auth(client: httpx.Client) -> None:
    r = client.get(f"/api/v1/clinical/fhir/Patient/{uuid.uuid4()}")
    assert r.status_code == 401


def test_fhir_patient_export(client: httpx.Client) -> None:
    pid, _, _ = _seed_fhir_fixtures()
    r = client.get(
        f"/api/v1/clinical/fhir/Patient/{pid}",
        headers=_headers(client, "doctor"),
    )
    assert r.status_code == 200, r.text
    assert FHIR_JSON in (r.headers.get("content-type") or "")
    body = r.json()
    assert body["resourceType"] == "Patient"
    assert body["id"] == pid
    assert body["identifier"][0]["value"].startswith("FHIR-")


def test_fhir_observation_from_image(client: httpx.Client) -> None:
    pid, iid, _ = _seed_fhir_fixtures()
    r = client.get(
        f"/api/v1/clinical/fhir/Observation/image/{iid}",
        headers=_headers(client, "doctor"),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["resourceType"] == "Observation"
    assert body["subject"]["reference"] == f"Patient/{pid}"
    assert body["valueCodeableConcept"]["coding"][0]["code"] == "H36.0"


def test_fhir_diagnostic_report(client: httpx.Client) -> None:
    pid, _, did = _seed_fhir_fixtures()
    r = client.get(
        f"/api/v1/clinical/fhir/DiagnosticReport/{did}",
        headers=_headers(client, "doctor"),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["resourceType"] == "DiagnosticReport"
    assert body["subject"]["reference"] == f"Patient/{pid}"
    assert "FHIR DiagnosticReport" in (body.get("conclusion") or "")


def test_fhir_patient_bundle(client: httpx.Client) -> None:
    pid, _, _ = _seed_fhir_fixtures()
    r = client.get(
        f"/api/v1/clinical/fhir/Patient/{pid}/bundle",
        headers=_headers(client, "doctor"),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["resourceType"] == "Bundle"
    types = {e["resource"]["resourceType"] for e in body["entry"]}
    assert "Patient" in types
    assert "Observation" in types or "DiagnosticReport" in types


def test_fhir_unit_patient_builder() -> None:
    from services.fhir_export import patient_to_fhir

    p = Patient(
        id="p1",
        patient_code="P0001",
        date_of_birth=date(1970, 1, 1),
    )
    f = patient_to_fhir(p)
    assert f["resourceType"] == "Patient"
    assert f["birthDate"] == "1970-01-01"
