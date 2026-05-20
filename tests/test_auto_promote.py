"""VISION 자동 승격 워크플로우 테스트 (D R2 Day 4).

테스트 철학 (Mock 0):
    - LLM/네트워크 호출 없음 — EyeImage 의 ``analysis_result`` 를 직접 JSON 으로 시드
    - ``try_auto_promote_for_image`` 함수를 단독 호출하고 DB 상태를 검증
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import date, datetime, timezone

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.requires_db]
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from config import get_settings
from models.clinical import DiagnosisReview, ReviewStatusEnum
from models.medical import (
    Diagnosis,
    EyeExam,
    EyeImage,
    ExamTypeEnum,
    ImageTypeEnum,
    Patient,
    ReportStatusEnum,
)
from services.auto_promote import try_auto_promote_for_image


def _async_db_url() -> str:
    url = get_settings().database_url
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


def _seed_patient_exam_image(
    *,
    analyzed: bool = True,
    confidence: float = 0.85,
    model_used: str = "consensus(gemma-4-26b-a4b,gpt-oss-20b,qwen3-4b-2507)",
    ontology_passed: bool = True,
    with_exam: bool = True,
) -> str:
    """1 Patient + 1 EyeExam(optional) + 1 EyeImage 를 시드하고 image_id 반환."""

    async def _do() -> str:
        eng = create_async_engine(_async_db_url(), poolclass=NullPool)
        SM = async_sessionmaker(eng, expire_on_commit=False)
        try:
            async with SM() as s:
                pcode = f"APR-{uuid.uuid4().hex[:6].upper()}"
                p = Patient(
                    id=str(uuid.uuid4()),
                    patient_code=pcode,
                    date_of_birth=date(1960, 1, 1),
                )
                s.add(p)
                await s.flush()

                exam_id: str | None = None
                if with_exam:
                    exam = EyeExam(
                        id=str(uuid.uuid4()),
                        patient_id=p.id,
                        exam_type=ExamTypeEnum.FUNDUS,
                        exam_date=date.today(),
                        raw_findings="auto-promote test",
                        report_status=ReportStatusEnum.PENDING,
                    )
                    s.add(exam)
                    await s.flush()
                    exam_id = exam.id

                analysis_payload = {
                    "condition": "diabetic_retinopathy",
                    "condition_kr": "당뇨망막병증",
                    "icd10_code": "H36.0",
                    "severity": "moderate",
                    "confidence": confidence,
                    "raw_analysis": "non-proliferative DR with microaneurysms.",
                    "ontology_passed": ontology_passed,
                    "model_used": model_used,
                }

                img = EyeImage(
                    id=str(uuid.uuid4()),
                    patient_id=p.id,
                    exam_id=exam_id,
                    image_type=ImageTypeEnum.FUNDUS,
                    file_path=f"/tmp/auto/{uuid.uuid4().hex}.jpg",
                    file_name="test.jpg",
                    file_size=1024,
                    mime_type="image/jpeg",
                    analyzed=analyzed,
                    analysis_icd_code="H36.0" if analyzed else None,
                    analysis_severity="moderate" if analyzed else None,
                    analysis_result=(
                        json.dumps(analysis_payload, ensure_ascii=False)
                        if analyzed
                        else None
                    ),
                    analyzed_at=(
                        datetime.now(timezone.utc) if analyzed else None
                    ),
                )
                s.add(img)
                await s.commit()
                return img.id
        finally:
            await eng.dispose()

    return asyncio.run(_do())


def _fetch_image_and_run_promote(image_id: str) -> dict:
    async def _do() -> dict:
        eng = create_async_engine(_async_db_url(), poolclass=NullPool)
        SM = async_sessionmaker(eng, expire_on_commit=False)
        try:
            async with SM() as s:
                img = await s.get(EyeImage, image_id)
                assert img is not None
                ap = await try_auto_promote_for_image(s, img)
                await s.commit()
                return ap
        finally:
            await eng.dispose()

    return asyncio.run(_do())


def _count_review_for_image(image_id: str) -> int:
    async def _do() -> int:
        eng = create_async_engine(_async_db_url(), poolclass=NullPool)
        SM = async_sessionmaker(eng, expire_on_commit=False)
        try:
            async with SM() as s:
                img = await s.get(EyeImage, image_id)
                if img is None or img.exam_id is None:
                    return 0
                diags = (
                    await s.scalars(
                        select(Diagnosis).where(Diagnosis.exam_id == img.exam_id)
                    )
                ).all()
                if not diags:
                    return 0
                reviews = (
                    await s.scalars(
                        select(DiagnosisReview).where(
                            DiagnosisReview.diagnosis_id.in_([d.id for d in diags])
                        )
                    )
                ).all()
                return len(reviews)
        finally:
            await eng.dispose()

    return asyncio.run(_do())


# ── 시나리오 ─────────────────────────────────────────────


def test_promotes_when_consensus_and_high_confidence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDI_AUTO_PROMOTE_ENABLED", "1")
    monkeypatch.setenv("MEDI_AUTO_PROMOTE_MIN_CONFIDENCE", "0.7")
    monkeypatch.setenv("MEDI_AUTO_PROMOTE_CONSENSUS_ONLY", "1")

    img_id = _seed_patient_exam_image(confidence=0.88)
    ap = _fetch_image_and_run_promote(img_id)
    assert ap["outcome"] == "promoted", ap
    assert _count_review_for_image(img_id) == 1


def test_skipped_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDI_AUTO_PROMOTE_ENABLED", "0")
    img_id = _seed_patient_exam_image(confidence=0.95)
    ap = _fetch_image_and_run_promote(img_id)
    assert ap["outcome"] == "skipped_disabled"
    assert _count_review_for_image(img_id) == 0


def test_skipped_when_low_confidence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDI_AUTO_PROMOTE_ENABLED", "1")
    monkeypatch.setenv("MEDI_AUTO_PROMOTE_MIN_CONFIDENCE", "0.7")
    img_id = _seed_patient_exam_image(confidence=0.55)
    ap = _fetch_image_and_run_promote(img_id)
    assert ap["outcome"] == "skipped_low_confidence", ap
    assert _count_review_for_image(img_id) == 0


def test_skipped_when_ontology_not_passed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDI_AUTO_PROMOTE_ENABLED", "1")
    monkeypatch.setenv("MEDI_AUTO_PROMOTE_MIN_CONFIDENCE", "0.6")
    img_id = _seed_patient_exam_image(confidence=0.99, ontology_passed=False)
    ap = _fetch_image_and_run_promote(img_id)
    assert ap["outcome"] == "skipped_low_confidence", ap
    assert _count_review_for_image(img_id) == 0


def test_skipped_when_non_consensus(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDI_AUTO_PROMOTE_ENABLED", "1")
    monkeypatch.setenv("MEDI_AUTO_PROMOTE_MIN_CONFIDENCE", "0.6")
    monkeypatch.setenv("MEDI_AUTO_PROMOTE_CONSENSUS_ONLY", "1")
    img_id = _seed_patient_exam_image(
        confidence=0.95, model_used="google/gemma-4-26b-a4b"
    )
    ap = _fetch_image_and_run_promote(img_id)
    assert ap["outcome"] == "skipped_non_consensus", ap
    assert _count_review_for_image(img_id) == 0


def test_promotes_non_consensus_when_toggle_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """``MEDI_AUTO_PROMOTE_CONSENSUS_ONLY=0`` 일 때는 단독 HEAVY 도 자동 promote."""
    monkeypatch.setenv("MEDI_AUTO_PROMOTE_ENABLED", "1")
    monkeypatch.setenv("MEDI_AUTO_PROMOTE_MIN_CONFIDENCE", "0.7")
    monkeypatch.setenv("MEDI_AUTO_PROMOTE_CONSENSUS_ONLY", "0")
    img_id = _seed_patient_exam_image(
        confidence=0.92, model_used="google/gemma-4-26b-a4b"
    )
    ap = _fetch_image_and_run_promote(img_id)
    assert ap["outcome"] == "promoted", ap
    assert _count_review_for_image(img_id) == 1


def test_skipped_when_no_exam(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDI_AUTO_PROMOTE_ENABLED", "1")
    monkeypatch.setenv("MEDI_AUTO_PROMOTE_MIN_CONFIDENCE", "0.5")
    img_id = _seed_patient_exam_image(confidence=0.95, with_exam=False)
    ap = _fetch_image_and_run_promote(img_id)
    assert ap["outcome"] == "skipped_no_exam", ap
    assert _count_review_for_image(img_id) == 0


def test_skipped_when_no_analysis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDI_AUTO_PROMOTE_ENABLED", "1")
    img_id = _seed_patient_exam_image(analyzed=False)
    ap = _fetch_image_and_run_promote(img_id)
    assert ap["outcome"] == "skipped_no_analysis", ap
    assert _count_review_for_image(img_id) == 0
