"""감사 로그 조회 — PartnerAnalysis.result_json audit_trail + 계정 등록."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.partner import PartnerAccount, PartnerAnalysis
from schemas.admin_audit import AuditLogEntryOut, AuditLogListResponse


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


async def load_audit_logs(
    db: AsyncSession,
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    decision: str | None = None,
    limit: int = 100,
) -> AuditLogListResponse:
    from_dt = _parse_dt(from_date)
    to_dt = _parse_dt(to_date)
    if to_dt and from_dt is None:
        to_dt = to_dt.replace(hour=23, minute=59, second=59)

    items: list[AuditLogEntryOut] = []

    accounts = (await db.execute(select(PartnerAccount).order_by(PartnerAccount.created_at.desc()))).scalars().all()
    for acc in accounts[:20]:
        created = acc.created_at
        if from_dt and created < from_dt:
            continue
        if to_dt and created > to_dt:
            continue
        items.append(
            AuditLogEntryOut(
                id=f"reg-{acc.id}",
                kind="partner_register",
                occurred_at=created.isoformat() if created else datetime.now(timezone.utc).isoformat(),
                partner_id=acc.partner_id,
                source="POST /api/v1/partner/register",
                detail=f"plan={acc.plan}",
            )
        )

    q = select(PartnerAnalysis).order_by(PartnerAnalysis.created_at.desc()).limit(limit)
    rows = (await db.execute(q)).scalars().all()

    for row in rows:
        created = row.created_at
        if from_dt and created and created < from_dt:
            continue
        if to_dt and created and created > to_dt:
            continue
        try:
            payload = json.loads(row.result_json or "{}")
        except json.JSONDecodeError:
            payload = {}
        audit = payload.get("audit_trail") or {}
        dec = audit.get("decision") or payload.get("decision")
        if decision and dec != decision:
            continue
        partner_id = payload.get("partner_id")
        items.append(
            AuditLogEntryOut(
                id=row.id,
                kind="partner_analyze",
                occurred_at=created.isoformat() if created else datetime.now(timezone.utc).isoformat(),
                partner_id=str(partner_id) if partner_id else None,
                patient_id=payload.get("patient_id"),
                decision=dec,
                reason=str(audit.get("reason") or ""),
                threshold=float(audit["threshold"]) if isinstance(audit.get("threshold"), (int, float)) else None,
                confidence=float(row.confidence) if row.confidence is not None else None,
                source="POST /api/v1/partner/analyze",
                detail=f"dr_grade={row.dr_grade} icd10={row.icd10_code}",
            )
        )

    items.sort(key=lambda x: x.occurred_at, reverse=True)
    return AuditLogListResponse(items=items[:limit], total=len(items[:limit]))
