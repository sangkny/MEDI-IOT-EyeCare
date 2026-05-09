# MEDI-IOT-EyeCare/models/medical.py
"""
SQLAlchemy ORM 모델 — 안과 의료 도메인

Patient    : 환자 기본 정보 (PII 암호화 저장)
EyeExam    : 안과 검사 기록 (OCT, 안저, 시야 검사 등)
Diagnosis  : AI 진단 결과 (LLM + OntologyValidator 검증)
"""
import uuid
from datetime import datetime, date

from sqlalchemy import (
    String, Text, Date, DateTime, Boolean,
    ForeignKey, Enum as SAEnum, Integer, Float,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import enum

from database import Base


# ════════════════════════════════════════════════════════════
# Enum 정의
# ════════════════════════════════════════════════════════════

class GenderEnum(str, enum.Enum):
    MALE   = "male"
    FEMALE = "female"
    OTHER  = "other"


class ExamTypeEnum(str, enum.Enum):
    FUNDUS      = "fundus"       # 안저 촬영
    OCT         = "oct"          # 빛간섭단층촬영
    VISUAL_FIELD = "visual_field" # 시야 검사
    SLIT_LAMP   = "slit_lamp"    # 세극등 검사
    REFRACTION  = "refraction"   # 굴절 검사
    IOP         = "iop"          # 안압 검사


class DiagnosisSeverityEnum(str, enum.Enum):
    NORMAL   = "normal"
    MILD     = "mild"
    MODERATE = "moderate"
    SEVERE   = "severe"
    CRITICAL = "critical"


class ReportStatusEnum(str, enum.Enum):
    PENDING    = "pending"    # LLM 생성 대기
    GENERATING = "generating" # LLM 생성 중
    COMPLETED  = "completed"  # 완료
    FAILED     = "failed"     # 실패


# ════════════════════════════════════════════════════════════
# 모델 정의
# ════════════════════════════════════════════════════════════

class Patient(Base):
    """
    환자 기본 정보

    주의: name, resident_number 등 PII는 암호화하여 저장.
    patient_code는 시스템 내부 식별자 (UUID).
    """
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    patient_code: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True,
        comment="병원 내부 환자 번호 (예: P123456)",
    )
    # PII 암호화 필드 (AES-256)
    name_encrypted: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="암호화된 환자 이름",
    )
    date_of_birth: Mapped[date | None] = mapped_column(
        Date, nullable=True,
    )
    gender: Mapped[GenderEnum | None] = mapped_column(
        SAEnum(GenderEnum), nullable=True,
    )
    primary_diagnosis_code: Mapped[str | None] = mapped_column(
        String(10), nullable=True,
        comment="주 진단 ICD 코드 (예: H36.0)",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # 관계
    exams: Mapped[list["EyeExam"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Patient code={self.patient_code}>"


class EyeExam(Base):
    """
    안과 검사 기록

    OCT, 안저, 시야 검사 등 다양한 검사 타입을 단일 테이블로 관리.
    검사 결과 원문(raw_findings)과 LLM 요약(summary)을 함께 저장.
    """
    __tablename__ = "eye_exams"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    patient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    exam_type: Mapped[ExamTypeEnum] = mapped_column(
        SAEnum(ExamTypeEnum), nullable=False,
    )
    exam_date: Mapped[date] = mapped_column(Date, nullable=False)
    icd_code: Mapped[str | None] = mapped_column(
        String(10), nullable=True,
        comment="검사 관련 ICD-10 코드",
    )

    # 검사 수치
    iop_left: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="좌안 안압 (mmHg)",
    )
    iop_right: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="우안 안압 (mmHg)",
    )
    visual_acuity_left: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="좌안 시력",
    )
    visual_acuity_right: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="우안 시력",
    )

    # 검사 소견
    raw_findings: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="검사 원시 소견 (의사 입력)",
    )
    ai_summary: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="LLM 생성 요약 소견",
    )
    report_status: Mapped[ReportStatusEnum] = mapped_column(
        SAEnum(ReportStatusEnum), default=ReportStatusEnum.PENDING,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # 관계
    patient: Mapped["Patient"] = relationship(back_populates="exams")
    diagnoses: Mapped[list["Diagnosis"]] = relationship(
        back_populates="exam", cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<EyeExam type={self.exam_type} date={self.exam_date}>"


class Diagnosis(Base):
    """
    AI 진단 결과

    shared-libraries Orchestrator(CONSENSUS 전략) + OntologyValidator로
    생성 및 검증된 진단 보고서.
    """
    __tablename__ = "diagnoses"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    exam_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("eye_exams.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    diagnosis_code: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="ICD-10 진단 코드",
    )
    diagnosis_name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="진단명",
    )
    severity: Mapped[DiagnosisSeverityEnum] = mapped_column(
        SAEnum(DiagnosisSeverityEnum), default=DiagnosisSeverityEnum.MILD,
    )
    report: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="LLM 생성 진단 보고서 (OntologyValidator 검증 완료)",
    )
    treatment_plan: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="치료 계획",
    )

    # LLM 생성 메타데이터
    llm_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    llm_iterations: Mapped[int] = mapped_column(Integer, default=1)
    llm_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    ontology_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence_score: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="진단 신뢰도 (0.0~1.0)",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    # 관계
    exam: Mapped["EyeExam"] = relationship(back_populates="diagnoses")

    def __repr__(self) -> str:
        return f"<Diagnosis code={self.diagnosis_code} severity={self.severity}>"
