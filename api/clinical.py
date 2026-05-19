"""MEDI 임상 연구 + 의사 검토 큐 라우트 (Phase 2 → D 트랙, 2026-05-12).

라우트:
    GET  /clinical/studies               — 임상 연구 목록 (Messidor-2 등)
    GET  /clinical/studies/{study_id}    — 단건
    POST /clinical/studies/{study_id}/memberships  — 이미지 ↔ 연구 매핑 (admin)
    GET  /clinical/studies/{study_id}/memberships  — 멤버십 목록
    POST /clinical/diagnoses/promote     — EyeImage 분석 → Diagnosis 승격 (doctor)
    POST /clinical/reviews/{review_id}/decide  — 의사 검토 결정 (doctor)
    GET  /clinical/reviews?status=...    — 검토 대기 큐
    GET  /clinical/fhir/...              — FHIR R4 export (D4, application/fhir+json)

의도:
    1. **임상 연구 (Clinical Study)** 는 Messidor-2 같은 외부 공개 데이터셋 또는
       자체 코호트의 메타. ground-truth 라벨이 있다면 AI 진단의 정확도와 비교 가능.
    2. **진단 승격 (Promotion)** — EyeImage 의 VISION 분석 결과를 정식 Diagnosis 로
       올린다. 자동으로 의사 검토 큐 (DiagnosisReview status='pending_review') 에 진입.
    3. **의사 검토** — doctor/admin role 만 approve/reject/needs_revision 결정 가능.
       AI 진단은 의사 검토를 거치지 않으면 정식 진단으로 사용되지 않는다 (의료 안전).
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from auth.dependencies import current_user_strict
from auth.policy import policy_require
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.clinical import (
    ClinicalStudy,
    ClinicalStudyMembership,
    DiagnosisReview,
    ReviewStatusEnum,
)
from models.medical import Diagnosis, DiagnosisSeverityEnum, EyeImage, EyeExam
from schemas.clinical import (
    DiagnosisPromoteRequest,
    DiagnosisPromoteResponse,
    MembershipCreate,
    MembershipOut,
    ReviewDecisionRequest,
    ReviewOut,
    ReviewQueueResponse,
    StudyListResponse,
    StudyOut,
)

from .fhir import router as fhir_router

log = logging.getLogger("api.clinical")
router = APIRouter()
router.include_router(fhir_router, prefix="/fhir", tags=["fhir"])


# ── Studies ────────────────────────────────────────────────


@router.get(
    "/studies",
    response_model=StudyListResponse,
    summary="임상 연구 목록 (Messidor-2 등)",
)
async def list_studies(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(current_user_strict),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
) -> StudyListResponse:
    stmt = select(ClinicalStudy).order_by(ClinicalStudy.code.asc())
    if status_filter:
        stmt = stmt.where(ClinicalStudy.status == status_filter)
    rows = await db.execute(stmt.limit(int(limit)))
    studies = [StudyOut.model_validate(s) for s in rows.scalars().all()]
    total = (await db.scalar(select(func.count(ClinicalStudy.id)))) or 0
    return StudyListResponse(studies=studies, total=int(total))


@router.get(
    "/studies/{study_id}",
    response_model=StudyOut,
    summary="임상 연구 단건",
)
async def get_study(
    study_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(current_user_strict),
) -> StudyOut:
    s = await db.get(ClinicalStudy, study_id)
    if not s:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="연구 없음")
    return StudyOut.model_validate(s)


# ── Memberships ───────────────────────────────────────────


@router.post(
    "/studies/{study_id}/memberships",
    response_model=MembershipOut,
    status_code=status.HTTP_201_CREATED,
    summary="이미지를 연구에 등록 + ground-truth 라벨 (admin)",
)
async def create_membership(
    study_id: str,
    body: MembershipCreate,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(policy_require("medi-iot", "create_exam")),
) -> MembershipOut:
    """관리자/연구자가 외부 데이터셋의 이미지를 연구에 등록.

    Messidor-2 의 1748 이미지를 한 번에 import 하는 일괄 라우트는 백로그.
    1 라운드는 단건 등록 (혹은 클라이언트 측 루프) 로 충분.
    """
    s = await db.get(ClinicalStudy, study_id)
    if not s:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="연구 없음")
    img = await db.get(EyeImage, body.image_id)
    if not img:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="이미지 없음")

    m = ClinicalStudyMembership(
        id=str(uuid.uuid4()),
        study_id=study_id,
        image_id=body.image_id,
        external_id=body.external_id,
        ground_truth_icd=body.ground_truth_icd,
        ground_truth_severity=body.ground_truth_severity,
        ground_truth_meta_json=body.ground_truth_meta_json,
    )
    db.add(m)
    s.image_count_loaded = (s.image_count_loaded or 0) + 1
    await db.flush()
    return MembershipOut.model_validate(m)


@router.get(
    "/studies/{study_id}/memberships",
    response_model=list[MembershipOut],
    summary="연구의 멤버십 목록",
)
async def list_memberships(
    study_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(current_user_strict),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[MembershipOut]:
    rows = await db.execute(
        select(ClinicalStudyMembership)
        .where(ClinicalStudyMembership.study_id == study_id)
        .order_by(ClinicalStudyMembership.created_at.desc())
        .limit(int(limit))
    )
    return [MembershipOut.model_validate(m) for m in rows.scalars().all()]


# ── Diagnosis Promotion (VISION 분석 → 정식 Diagnosis) ────


@router.post(
    "/diagnoses/promote",
    response_model=DiagnosisPromoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="EyeImage VISION 분석을 정식 Diagnosis 로 승격 + 검토 큐 진입",
)
async def promote_to_diagnosis(
    body: DiagnosisPromoteRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "promote_diagnosis")),
) -> DiagnosisPromoteResponse:
    """EyeImage 의 자동 분석 결과를 정식 Diagnosis 로 승격하고
    자동으로 의사 검토 큐 (DiagnosisReview, status='pending_review') 에 진입시킨다.

    승격 조건:
        - EyeImage 의 ``analyzed=True``
        - ``analysis_icd_code`` 가 채워져 있을 것 (VISION 분석 완료)
        - 지정된 EyeExam 이 같은 환자에 속할 것
    """
    img = await db.get(EyeImage, body.image_id)
    if not img:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="이미지 없음")
    if not img.analyzed or not img.analysis_icd_code:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="이미지가 아직 VISION 분석되지 않았거나 ICD 코드가 비어있음",
        )
    exam = await db.get(EyeExam, body.exam_id)
    if not exam:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="검사 없음")
    if exam.patient_id != img.patient_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="이미지와 검사의 환자가 일치하지 않음",
        )

    try:
        data = json.loads(img.analysis_result or "{}")
    except json.JSONDecodeError:
        data = {}

    severity = (
        img.analysis_severity
        or data.get("severity")
        or DiagnosisSeverityEnum.MILD.value
    )
    diagnosis_name = (
        data.get("condition_kr") or data.get("condition") or "VISION 분석 진단"
    )

    sev_enum: DiagnosisSeverityEnum
    try:
        sev_enum = DiagnosisSeverityEnum(severity)
    except ValueError:
        sev_enum = DiagnosisSeverityEnum.MILD

    diag = Diagnosis(
        id=str(uuid.uuid4()),
        exam_id=body.exam_id,
        diagnosis_code=img.analysis_icd_code,
        diagnosis_name=str(diagnosis_name)[:200],
        severity=sev_enum,
        report=str(data.get("brief_summary") or data.get("raw_analysis") or "")[:8000],
        treatment_plan=body.treatment_plan,
        llm_model=data.get("model_used"),
        llm_iterations=1,
        ontology_passed=bool(data.get("ontology_passed", False)),
        confidence_score=float(data.get("confidence") or 0.0),
    )
    db.add(diag)
    await db.flush()

    review = DiagnosisReview(
        id=str(uuid.uuid4()),
        diagnosis_id=diag.id,
        status=ReviewStatusEnum.PENDING_REVIEW.value,
    )
    db.add(review)
    await db.flush()

    log.info(
        "Diagnosis 승격: diag=%s review=%s icd=%s severity=%s by=%s",
        diag.id[:8], review.id[:8], diag.diagnosis_code, sev_enum.value,
        user.get("user_id"),
    )
    return DiagnosisPromoteResponse(
        diagnosis_id=diag.id,
        review_id=review.id,
        review_status=review.status,
        diagnosis_code=diag.diagnosis_code,
        severity=sev_enum.value,
    )


# ── Diagnosis Review (의사 검토) ────────────────────────


@router.get(
    "/reviews",
    response_model=ReviewQueueResponse,
    summary="의사 검토 큐 (기본 status=pending_review)",
)
async def list_reviews(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(current_user_strict),
    status_filter: str = Query(default="pending_review", alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
) -> ReviewQueueResponse:
    rows = await db.execute(
        select(DiagnosisReview)
        .where(DiagnosisReview.status == status_filter)
        .order_by(DiagnosisReview.created_at.asc())
        .limit(int(limit))
    )
    reviews = [ReviewOut.model_validate(r) for r in rows.scalars().all()]
    total = (
        await db.scalar(
            select(func.count(DiagnosisReview.id)).where(
                DiagnosisReview.status == status_filter
            )
        )
    ) or 0
    return ReviewQueueResponse(reviews=reviews, total=int(total))


@router.get(
    "/reviews/{review_id}",
    response_model=ReviewOut,
    summary="의사 검토 단건 조회",
)
async def get_review(
    review_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(current_user_strict),
) -> ReviewOut:
    review = await db.get(DiagnosisReview, review_id)
    if not review:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="검토 없음")
    return ReviewOut.model_validate(review)


@router.post(
    "/reviews/{review_id}/decide",
    response_model=ReviewOut,
    summary="의사 검토 결정 (approve/reject/needs_revision)",
)
async def decide_review(
    review_id: str,
    body: ReviewDecisionRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "review_diagnosis")),
) -> ReviewOut:
    review = await db.get(DiagnosisReview, review_id)
    if not review:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="검토 없음")
    if review.status != ReviewStatusEnum.PENDING_REVIEW.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"이미 결정됨 (status={review.status})",
        )

    review.status = body.status
    review.reviewed_by = str(user.get("user_id", ""))
    review.reviewed_at = datetime.now(timezone.utc)
    review.review_notes = body.review_notes
    await db.flush()
    await db.refresh(review)

    log.info(
        "Diagnosis 검토: review=%s status=%s by=%s",
        review.id[:8], review.status, review.reviewed_by,
    )
    return ReviewOut(
        id=review.id,
        diagnosis_id=review.diagnosis_id,
        status=review.status,
        reviewed_by=review.reviewed_by,
        reviewed_at=review.reviewed_at,
        review_notes=review.review_notes,
        created_at=review.created_at,
        updated_at=review.updated_at,
    )
