# MEDI-IOT-EyeCare/schemas/medical.py
"""
Pydantic 스키마 — API 요청/응답 직렬화

원칙:
  - Response 스키마는 PII(이름 등)를 마스킹하거나 제외
  - 모든 날짜는 ISO 8601 형식
  - 진단 코드는 ICD-10 형식 검증
  - json_schema_extra 로 Swagger UI에 예시값 표시
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
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "patient_code": "P123456",
                "name": "홍길동",
                "date_of_birth": "1975-03-15",
                "gender": "male",
                "primary_diagnosis_code": "H36.0",
                "notes": "당뇨병 10년 이력, 정기 안저 검사 중",
            }
        }
    )

    patient_code: Annotated[str, Field(
        min_length=3, max_length=20,
        examples=["P123456"],
        description="병원 내부 환자 번호 (3~20자, 고유값)",
    )]
    name: Annotated[str | None, Field(
        default=None, max_length=50,
        description="환자 이름 (AES-256 암호화 저장, 응답 시 마스킹)",
    )]
    date_of_birth: Annotated[date | None, Field(
        default=None,
        description="생년월일 (YYYY-MM-DD)",
        examples=["1975-03-15"],
    )]
    gender: Annotated[str | None, Field(
        default=None,
        pattern="^(male|female|other)$",
        description="성별: male | female | other",
    )]
    primary_diagnosis_code: Annotated[str | None, Field(
        default=None,
        description="주 진단 ICD-10 코드 (예: H36.0 당뇨망막병증)",
        examples=["H36.0"],
    )]
    notes: Annotated[str | None, Field(
        default=None,
        description="임상 메모 (암호화 저장 대상 아님)",
    )]

    @field_validator("primary_diagnosis_code")
    @classmethod
    def validate_diagnosis_code(cls, v: str | None) -> str | None:
        return validate_icd_code(v)


class PatientResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "patient_code": "P123456",
                "name_masked": "홍**",
                "date_of_birth": "1975-03-15",
                "gender": "male",
                "primary_diagnosis_code": "H36.0",
                "is_active": True,
                "created_at": "2026-05-09T10:30:00Z",
                "exam_count": 3,
            }
        },
    )

    id: str = Field(description="환자 UUID")
    patient_code: str = Field(description="병원 내부 환자 번호")
    name_masked: str | None = Field(default=None, description="마스킹된 이름 (첫 글자 + *)")
    date_of_birth: date | None = Field(default=None, description="생년월일")
    gender: str | None = Field(default=None, description="성별")
    primary_diagnosis_code: str | None = Field(default=None, description="주 진단 ICD-10 코드")
    is_active: bool = Field(description="활성 여부 (false = soft delete)")
    created_at: datetime = Field(description="등록일시 (UTC)")
    exam_count: int = Field(default=0, description="검사 기록 수")


# ════════════════════════════════════════════════════════════
# EyeExam 스키마
# ════════════════════════════════════════════════════════════

class ExamCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "patient_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "exam_type": "fundus",
                "exam_date": "2026-05-09",
                "icd_code": "H36.0",
                "iop_left": 14.5,
                "iop_right": 15.2,
                "visual_acuity_left": "0.8",
                "visual_acuity_right": "0.7",
                "raw_findings": (
                    "우안: 황반 주위 점상출혈 및 경성삼출물 다수 관찰. "
                    "신생혈관 의심 소견. "
                    "좌안: 경미한 미세동맥류 관찰."
                ),
            }
        }
    )

    patient_id: str = Field(description="환자 UUID (patients.id)")
    exam_type: Annotated[str, Field(
        pattern="^(fundus|oct|visual_field|slit_lamp|refraction|iop)$",
        description=(
            "검사 종류:\n"
            "- fundus: 안저 촬영\n"
            "- oct: 빛간섭단층촬영\n"
            "- visual_field: 시야 검사\n"
            "- slit_lamp: 세극등 검사\n"
            "- refraction: 굴절 검사\n"
            "- iop: 안압 검사"
        ),
        examples=["fundus"],
    )]
    exam_date: date = Field(description="검사 날짜 (YYYY-MM-DD)")
    icd_code: Annotated[str | None, Field(
        default=None,
        description="ICD-10 코드 (예: H36.0, H40.1)",
        examples=["H36.0"],
    )]
    iop_left: float | None = Field(
        default=None, ge=0, le=80,
        description="좌안 안압 (mmHg, 정상 범위: 10~21)",
    )
    iop_right: float | None = Field(
        default=None, ge=0, le=80,
        description="우안 안압 (mmHg)",
    )
    visual_acuity_left: str | None = Field(
        default=None, max_length=10,
        description="좌안 교정시력 (예: 0.8, 1.0, 0.1)",
    )
    visual_acuity_right: str | None = Field(
        default=None, max_length=10,
        description="우안 교정시력",
    )
    raw_findings: str | None = Field(
        default=None, max_length=5000,
        description="의사가 직접 입력한 검사 소견 원문 (AI 분석 기반 데이터)",
    )

    @field_validator("icd_code")
    @classmethod
    def validate_icd(cls, v: str | None) -> str | None:
        return validate_icd_code(v)


class ExamResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                "patient_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "exam_type": "fundus",
                "exam_date": "2026-05-09",
                "icd_code": "H36.0",
                "iop_left": 14.5,
                "iop_right": 15.2,
                "visual_acuity_left": "0.8",
                "visual_acuity_right": "0.7",
                "raw_findings": "우안: 황반 주위 점상출혈 및 경성삼출물 다수 관찰.",
                "ai_summary": "당뇨망막병증 비증식성 중등도 소견. 추가 OCT 권장.",
                "report_status": "completed",
                "created_at": "2026-05-09T10:35:00Z",
            }
        },
    )

    id: str = Field(description="검사 UUID")
    patient_id: str = Field(description="환자 UUID")
    exam_type: str = Field(description="검사 종류")
    exam_date: date = Field(description="검사 날짜")
    icd_code: str | None = Field(description="ICD-10 코드")
    iop_left: float | None = Field(description="좌안 안압 (mmHg)")
    iop_right: float | None = Field(description="우안 안압 (mmHg)")
    visual_acuity_left: str | None = Field(description="좌안 시력")
    visual_acuity_right: str | None = Field(description="우안 시력")
    raw_findings: str | None = Field(description="검사 소견 원문")
    ai_summary: str | None = Field(description="LLM 생성 요약 (최대 500자)")
    report_status: str = Field(
        description="보고서 상태: pending | generating | completed | failed"
    )
    created_at: datetime = Field(description="등록일시 (UTC)")


# ════════════════════════════════════════════════════════════
# Diagnosis 스키마
# ════════════════════════════════════════════════════════════

class DiagnosisRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "exam_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                "additional_context": "환자 HbA1c 8.2%, 당뇨병 진단 12년차, 인슐린 치료 중",
                "strategy": "consensus",
            }
        }
    )

    exam_id: str = Field(description="AI 분석할 검사 기록 UUID (eye_exams.id)")
    additional_context: Annotated[str | None, Field(
        default=None,
        max_length=1000,
        description="추가 임상 맥락 (혈당 수치, 복약 이력 등 — AI 정확도 향상에 도움)",
    )]
    strategy: Annotated[str, Field(
        default="consensus",
        pattern="^(pipeline|consensus|debate|fastest)$",
        description=(
            "Orchestrator 전략:\n"
            "- **consensus** (권장): FAST+HEAVY 두 모델 합의 — 의료 안전 최적\n"
            "- pipeline: 순차 실행 (Planner→Generator→Reviewer→Fixer)\n"
            "- debate: 두 모델 논쟁 후 합의\n"
            "- fastest: 가장 빠른 모델 단독 실행 (응급 상황)"
        ),
        examples=["consensus"],
    )]


class DiagnosisResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
                "exam_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                "diagnosis_code": "H36.0",
                "diagnosis_name": "당뇨망막병증",
                "severity": "moderate",
                "report": (
                    "## 안과 진단 보고서\n\n"
                    "**진단**: 비증식성 당뇨망막병증 중등도 (H36.0)\n\n"
                    "**소견 요약**: 우안에서 황반 주위 점상출혈 및 경성삼출물이 "
                    "다수 관찰되며, 신생혈관 의심 소견이 있습니다. "
                    "좌안은 경미한 미세동맥류 소견입니다.\n\n"
                    "**중증도**: 중등도 — 즉각적인 안과 전문의 추적 관찰 필요\n\n"
                    "**치료 권고**: 범망막광응고술(PRP) 시술 고려, "
                    "내분비과 협진을 통한 혈당 조절 강화"
                ),
                "treatment_plan": "3개월 내 범망막광응고술(PRP) 시술 검토. 혈당 목표 HbA1c < 7%.",
                "llm_model": "google/gemma-4-26b-a4b",
                "llm_iterations": 1,
                "llm_latency_ms": 85420.5,
                "ontology_passed": True,
                "confidence_score": 0.85,
                "created_at": "2026-05-09T10:40:00Z",
            }
        },
    )

    id: str = Field(description="진단 UUID")
    exam_id: str = Field(description="관련 검사 UUID")
    diagnosis_code: str = Field(description="ICD-10 진단 코드 (예: H36.0)")
    diagnosis_name: str = Field(description="진단명 (한국어)")
    severity: str = Field(
        description="중증도: normal | mild | moderate | severe | critical"
    )
    report: str | None = Field(
        description="LLM 생성 진단 보고서 전문 (OntologyValidator 검증 완료, 최대 2000자)"
    )
    treatment_plan: str | None = Field(description="치료 계획 및 추적 관찰 권고")
    llm_model: str | None = Field(description="보고서 생성에 사용된 LLM 모델명")
    llm_iterations: int = Field(description="Orchestrator 반복 횟수 (1 = 첫 시도 통과)")
    llm_latency_ms: float | None = Field(description="LLM 처리 시간 (밀리초)")
    ontology_passed: bool = Field(
        description="OntologyValidator MEDICAL 도메인 검증 통과 여부"
    )
    confidence_score: float | None = Field(
        description="진단 신뢰도 (0.0~1.0, ontology_passed=True면 0.85+)"
    )
    created_at: datetime = Field(description="생성일시 (UTC)")


# ════════════════════════════════════════════════════════════
# 공통 응답
# ════════════════════════════════════════════════════════════

class HealthResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "ok",
                "service": "medi-iot",
                "version": "0.1.0",
                "llm_provider": "local",
                "db_connected": True,
                "timestamp": "2026-05-09T01:30:48Z",
            }
        }
    )

    status: str = Field(description="서비스 상태: ok | degraded | error")
    service: str = Field(description="서비스 이름")
    version: str = Field(description="API 버전")
    llm_provider: str = Field(description="LLM Provider: local | openai | anthropic")
    db_connected: bool = Field(description="PostgreSQL 연결 상태")
    timestamp: datetime = Field(description="응답 시각 (UTC)")
