"""Admin audit log list response."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


AuditDecision = Literal["APPROVE", "REVISE", "REJECT"]
AuditEventKind = Literal["pipeline", "partner_register", "partner_analyze", "review"]


class AuditLogEntryOut(BaseModel):
    id: str
    kind: AuditEventKind
    occurred_at: str
    patient_id: str | None = None
    partner_id: str | None = None
    decision: AuditDecision | None = None
    reason: str | None = None
    threshold: float | None = None
    confidence: float | None = None
    source: str
    detail: str | None = None


class AuditLogListResponse(BaseModel):
    items: list[AuditLogEntryOut]
    total: int = Field(ge=0)
