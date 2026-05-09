# MEDI-IOT-EyeCare/schemas/medical.py
"""
Pydantic 스키마 — API 요청/응답 직렬화

원칙:
  - Response 스키마는 PII(이름 등)를 마스킹하거나 제외
  - 모든 날짜는 ISO 8601 형식
  - 진단 코드는 ICD-10 형식 검증
"""
import re
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, ConfigDict


# ════════════════════════════════════════════════════════════
# 공통
# ════════════════════════════════════════════════════════════

ICD_CODE_PATTERN = re.compile(r"^[A-Z]\d{2}(\.\d{1,2})?$")


def validate_icd_code(v: str | None) -> str | None:
    if v is None:
        return v
    if not ICD_CODE_PATTERN.match(v.upper()):
        raise ValueError(f"유효하지 않은 ICD-10 코드: {v} (예: H36.0)")
    return v.upper()


# ════════════════════════════════════════════════════════════
# Patient 스키마
# ════════════════════════════════════════════════════════════

class PatientCreate(BaseModel):
    patient_code: Annotated[str, Field(
        min_length=3, max_length=20,
        examples=["P123456"],
        description="병원 내부 환자 번호",
    )]
    name: Annotated[str | None, Field(
        default=None, max_length=50,
        description="환자 이름 (암호화 저장)",
    )]
    date_of_birth: date | None = None
    gender: Annotated[str | None, Field(
        default=None,
        pattern="^(male|female|other)$",
    )]
    primary_diagnosis_code: str | None = None
    notes: str | None = None

    @field_validator("primary_diagnosis_code")
    @classmethod
    def validate_diagnosis_code(cls, v: str | None) -> str | None:
        return validate_icd_code(v)


class PatientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_code: str
    # 이름은 마스킹 처리 (첫 글자만 노출)
    name_masked: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    primary_diagnosis_code: str | None = None
    is_active: bool
    created_at: datetime
    exam_count: int = 0


# ════════════════════════════════════════════════════════════
# EyeExam 스키마
# ════════════════════════════════════════════════════════════

class ExamCreate(BaseModel):
    patient_id: str = Field(description="환자 UUID")
    exam_type: Annotated[str, Field(
        pattern="^(fundus|oct|visual_field|slit_lamp|refraction|iop)$",
        description="검사 종류",
    )]
    exam_date: date
    icd_code: str | None = None
    iop_left: float | None = Field(default=None, ge=0, le=80, description="좌안 안압 mmHg")
    iop_right: float | None = Field(default=None, ge=0, le=80, description="우안 안압 mmHg")
    visual_acuity_left: str | None = Field(default=None, max_length=10)
    visual_acuity_right: str | None = Field(default=None, max_length=10)
    raw_findings: str | None = Field(default=None, max_length=5000)

    @field_validator("icd_code")
    @classmethod
    def validate_icd(cls, v: str | None) -> str | None:
        return validate_icd_code(v)


class ExamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str
    exam_type: str
    exam_date: date
    icd_code: str | None
    iop_left: float | None
    iop_right: float | None
    visual_acuity_left: str | None
    visual_acuity_right: str | None
    raw_findings: str | None
    ai_summary: str | None
    report_status: str
    created_at: datetime


# ════════════════════════════════════════════════════════════
# Diagnosis 스키마
# ════════════════════════════════════════════════════════════

class DiagnosisRequest(BaseModel):
    exam_id: str = Field(description="검사 UUID")
    additional_context: str | None = Field(
        default=None,
        max_length=1000,
        description="추가 임상 맥락 (의사 메모 등)",
    )
    strategy: Annotated[str, Field(
        default="consensus",
        pattern="^(pipeline|consensus|debate|fastest)$",
        description="Orchestrator 전략 (의료: consensus 권장)",
    )]


class DiagnosisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    exam_id: str
    diagnosis_code: str
    diagnosis_name: str
    severity: str
    report: str | None
    treatment_plan: str | None
    llm_model: str | None
    llm_iterations: int
    llm_latency_ms: float | None
    ontology_passed: bool
    confidence_score: float | None
    created_at: datetime


# ════════════════════════════════════════════════════════════
# 공통 응답
# ════════════════════════════════════════════════════════════

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    llm_provider: str
    db_connected: bool
    timestamp: datetime
