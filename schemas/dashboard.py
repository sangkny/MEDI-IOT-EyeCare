"""대시보드 API 응답 스키마 (Week 4)."""
from __future__ import annotations

from datetime import date as Date, datetime as DateTime

from pydantic import BaseModel, Field


class DiagnosisBucket(BaseModel):
    """진단 카테고리별 건수 (최근 30일 diagnoses 기준)."""

    key: str = Field(description="내부 키: diabetic_retinopathy | macular | glaucoma | normal | other")
    label_kr: str = Field(description="한글 라벨")
    count: int = Field(ge=0)


class ExamIcdAgreementStats(BaseModel):
    """
    AI 진단과 검사에 기록된 ICD-10 간 일치 비율 (의사 금표 진단 미저장 때의 프록시).
    동일 검사 레코드에 대해 `eye_exams.icd_code`가 있고 해당 진단 코드가 존재할 때만 포함.
    """

    compared_pairs: int = Field(description="비교 가능한 진단 레코드 수")
    matched_pairs: int = Field(description="검사 ICD와 AI diagnosis_code 코드가 동일한 건수 (대문자 무시)")
    agreement_rate: float | None = Field(
        default=None,
        description="matched/compared 비율, 0.0~1.0. 없으면 비교 샘플 부족.",
    )
    note: str = Field(
        default="실제 의사 최종 판단 필드 연동 후 정확도를 재계산할 수 있습니다.",
    )


class DashboardStatsResponse(BaseModel):
    stats_date_local_utc: str = Field(description="집계 기준일 (UTC, YYYY-MM-DD)")
    exams_today: int = Field(ge=0, description="오늘(UTC) 시작 이후 검사 건수")
    new_patients_today: int = Field(ge=0, description="오늘(UTC) 시작 이후 신규 환자 등록 건수")
    diagnosis_buckets: list[DiagnosisBucket] = Field(
        description="최근 30일 diagnoses 기준 카테고리 분포",
    )
    ai_icd_agreement_vs_exam: ExamIcdAgreementStats


class DashboardAlert(BaseModel):
    patient_id: str
    patient_code: str
    reason: str = Field(description="알림 사유 요약")
    severity: str = Field(description="urgent | warning | info")


class DashboardAlertsResponse(BaseModel):
    generated_at: DateTime
    urgent_tracking: list[DashboardAlert] = Field(
        description="안압/시력 악화 추세 또는 중증 진단 후 추적 권장 대상",
    )
    ontology_validator_warnings: list[DashboardAlert] = Field(
        description="ontology_passed=false 인 최근 AI 진단",
    )


class ProviderUsageRow(BaseModel):
    provider_key: str
    calls_today: int = Field(ge=0)
    estimated_tokens_today: int = Field(ge=0)


class DashboardLLMUsageResponse(BaseModel):
    date: Date = Field(description="UTC 일자 기준 통계 버킷")
    calls_today: int = Field(ge=0)
    total_tokens_estimated: int = Field(ge=0)
    by_provider: list[ProviderUsageRow]
    aggregation_note: str


__all__ = [
    "DiagnosisBucket",
    "ExamIcdAgreementStats",
    "DashboardStatsResponse",
    "DashboardAlert",
    "DashboardAlertsResponse",
    "ProviderUsageRow",
    "DashboardLLMUsageResponse",
]
