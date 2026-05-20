"""SaMD 파트너 계정·분석 과금 기록 ORM."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from database import Base


class PartnerPlanEnum(str, enum.Enum):
    TRIAL = "trial"
    STANDARD = "standard"
    ENTERPRISE = "enterprise"


class PartnerAccount(Base):
    __tablename__ = "partner_accounts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    partner_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True,
        comment="외부 파트너 식별자 (예: acme-clinic)",
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    api_key_hash: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True,
        comment="SHA-256(api_key) — 평문 키는 저장하지 않음",
    )
    plan: Mapped[str] = mapped_column(
        String(32), default=PartnerPlanEnum.TRIAL.value, nullable=False
    )
    cost_per_analysis: Mapped[float] = mapped_column(
        Float, default=0.05, nullable=False,
        comment="건당 과금 (USD, 스모크 기본값)",
    )
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PartnerAnalysis(Base):
    __tablename__ = "partner_analyses"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    partner_account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("partner_accounts.id"), nullable=False, index=True
    )
    analysis_type: Mapped[str] = mapped_column(String(32), default="fundus")
    return_format: Mapped[str] = mapped_column(String(16), default="json")
    dr_grade: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    icd10_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    severity: Mapped[str | None] = mapped_column(String(32), nullable=True)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
