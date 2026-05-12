"""MEDI 임상 연구 + 의사 검토 큐 스키마 (Phase 2 → D 트랙, 2026-05-12)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ── ClinicalStudy ────────────────────────────────────────────


class StudyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    description: str | None
    source_url: str | None
    license: str | None
    image_count_total: int
    image_count_loaded: int
    label_schema_json: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class StudyListResponse(BaseModel):
    studies: list[StudyOut]
    total: int


# ── Membership ──────────────────────────────────────────────


class MembershipCreate(BaseModel):
    image_id: str = Field(..., min_length=8, max_length=36)
    external_id: str | None = Field(default=None, max_length=128)
    ground_truth_icd: str | None = Field(default=None, max_length=16)
    ground_truth_severity: Literal[
        "normal", "mild", "moderate", "severe", "critical"
    ] | None = None
    ground_truth_meta_json: str | None = None


class MembershipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    study_id: str
    image_id: str
    external_id: str | None
    ground_truth_icd: str | None
    ground_truth_severity: str | None
    created_at: datetime


# ── Diagnosis Promotion (이미지 분석 → 정식 Diagnosis + 검토 큐) ──


class DiagnosisPromoteRequest(BaseModel):
    """EyeImage 의 VISION 분석을 정식 Diagnosis 로 승격.

    승격 시:
        1. Diagnosis row 생성 (image 의 analysis_icd_code, severity, raw 사용)
        2. DiagnosisReview row 생성 (status=pending_review)
        3. 의사 검토 큐 진입
    """

    image_id: str = Field(..., min_length=8, max_length=36)
    exam_id: str = Field(..., min_length=8, max_length=36)
    treatment_plan: str | None = Field(default=None, max_length=4000)


class DiagnosisPromoteResponse(BaseModel):
    diagnosis_id: str
    review_id: str
    review_status: str
    diagnosis_code: str
    severity: str


# ── Diagnosis Review (의사 검토) ─────────────────────────────


class ReviewDecisionRequest(BaseModel):
    """의사 검토 결정.

    status 전이:
        pending_review → approved | rejected | needs_revision
    """

    status: Literal["approved", "rejected", "needs_revision"]
    review_notes: str | None = Field(default=None, max_length=4000)


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    diagnosis_id: str
    status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_notes: str | None
    created_at: datetime
    updated_at: datetime


class ReviewQueueResponse(BaseModel):
    reviews: list[ReviewOut]
    total: int
