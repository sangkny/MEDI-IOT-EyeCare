"""MEDI 임상 연구 코호트 + 의사 검토 워크플로 (Phase 2 → D 트랙, 2026-05-12).

기존 ``models/medical.py`` (Patient/EyeExam/Diagnosis/EyeImage) 가 *환자 단위*
ORM 인 반면, 이 모듈은 *데이터셋 단위* 의 임상 연구 메타를 다룬다.

- ``ClinicalStudy`` — Messidor-2 / Kaggle DR / 자체 코호트 등 외부 또는 내부 데이터셋
  메타. 라이선스·출처·라벨 스키마를 시드한다.
- ``ClinicalStudyMembership`` — 이미지 ↔ 연구 M:N 매핑 + ground-truth 라벨
  (외부 데이터셋의 정답 라벨을 보관해 AI 진단의 정확도를 비교 가능).
- ``DiagnosisReview`` — Diagnosis 의 의사 검토 큐. AI 가 자동 생성한 진단은
  의사가 approve/reject 해야 정식 진단이 된다 (의료 안전 — 한장요약 §"의사 검토 필수").

기존 ``Diagnosis`` 모델은 변경 없이 둔다 — 1:1 sidecar (``DiagnosisReview``) 로
의사 검토 컬럼을 분리해 기존 검사·진단 워크플로 (88/88 PASS) 의 회귀 위험을 0
으로 유지한다.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime, ForeignKey, Integer, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


# ════════════════════════════════════════════════════════════
# Enums
# ════════════════════════════════════════════════════════════


class StudyStatusEnum(str, enum.Enum):
    """임상 연구 라이프사이클 상태."""

    DRAFT = "draft"          # 메타만 등록, 이미지 import 전
    LOADING = "loading"      # 이미지 import 진행 중
    READY = "ready"          # 분석 준비 완료
    ARCHIVED = "archived"    # 사용 중단


class ReviewStatusEnum(str, enum.Enum):
    """의사 검토 상태 머신.

    pending_review → (의사 검토) → approved | rejected | needs_revision
    """

    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


# ════════════════════════════════════════════════════════════
# ORM
# ════════════════════════════════════════════════════════════


class ClinicalStudy(Base):
    """임상 연구 코호트 — 외부 공개 데이터셋 또는 내부 환자 그룹.

    여러 ``EyeImage`` 가 한 ``ClinicalStudy`` 에 속할 수 있고,
    한 이미지가 여러 연구 (multi-cohort) 에 참여할 수도 있어 M:N (``ClinicalStudyMembership``).
    """

    __tablename__ = "clinical_studies"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    code: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True,
        comment="식별 코드 (예: 'messidor-2', 'kaggle-dr-2019')",
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="원본 출처 또는 라이선스 페이지",
    )
    license: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="라이선스 식별자 (예: 'CC BY 4.0')",
    )
    image_count_total: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="원본 데이터셋의 전체 이미지 수 (예: Messidor-2 = 1748)",
    )
    image_count_loaded: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="현재 시스템에 import 된 이미지 수",
    )
    label_schema_json: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="라벨 스키마 JSON (예: {'dr_grade': [0,1,2,3,4], 'me_grade': [0,1]})",
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=StudyStatusEnum.DRAFT.value,
        index=True,
        comment="StudyStatusEnum value (draft|loading|ready|archived) — app-level enum",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

    memberships: Mapped[list["ClinicalStudyMembership"]] = relationship(
        back_populates="study", cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ClinicalStudy code={self.code} status={self.status}>"


class ClinicalStudyMembership(Base):
    """이미지가 임상 연구에 속한다는 매핑 + ground-truth 라벨."""

    __tablename__ = "clinical_study_memberships"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    study_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clinical_studies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    image_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("eye_images.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    external_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        comment="원본 데이터셋의 식별자 (예: 'IM000312' Messidor 파일명)",
    )
    ground_truth_icd: Mapped[str | None] = mapped_column(
        String(16), nullable=True,
        comment="원본 데이터셋의 정답 ICD-10 (학습/평가용)",
    )
    ground_truth_severity: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        comment="원본 정답 중증도 (예: 'moderate' DR grade=2)",
    )
    ground_truth_meta_json: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="라벨 풀 JSON (DR grade / ME grade / age / sex 등)",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    study: Mapped["ClinicalStudy"] = relationship(back_populates="memberships")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Membership study={self.study_id[:8]} img={self.image_id[:8]}>"


class DiagnosisReview(Base):
    """AI 진단의 의사 검토 큐 — Diagnosis 의 1:1 sidecar.

    AI 가 자동 생성한 ``Diagnosis`` 는 ``pending_review`` 로 진입하며,
    의사가 ``approved``/``rejected``/``needs_revision`` 으로 전이시킨다.
    의사 ID·검토 시각·검토 노트는 감사 추적용.
    """

    __tablename__ = "diagnosis_reviews"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    diagnosis_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("diagnoses.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
        comment="1:1 관계 (Diagnosis 당 검토 1개)",
    )
    status: Mapped[str] = mapped_column(
        String(24), nullable=False,
        default=ReviewStatusEnum.PENDING_REVIEW.value, index=True,
        comment="ReviewStatusEnum value (pending_review|approved|rejected|needs_revision)",
    )
    reviewed_by: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
        comment="검토 의사 user_id (auth.dependencies)",
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    review_notes: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="검토 코멘트 (반려/수정 사유 포함)",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<DiagnosisReview diagnosis={self.diagnosis_id[:8]} status={self.status}>"
        )


__all__ = [
    "ClinicalStudy",
    "ClinicalStudyMembership",
    "DiagnosisReview",
    "StudyStatusEnum",
    "ReviewStatusEnum",
]
