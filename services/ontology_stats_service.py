"""Ontology 검증 통계 — AI 진단(Diagnosis) 기준 일간 집계."""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.medical import Diagnosis
from schemas.ontology import (
    OntologyDomainSlice,
    OntologyErrorBucket,
    OntologyStatsResponse,
)

_CODE_RE = re.compile(r"\b([A-Z]{2,10}-(?:STR|SEM|SYN|FMT|DEP|SEC|BUS|POL|COS|SVG|POLY)-?\d+)\b")


def _utc_today_floor() -> datetime:
    n = datetime.now(timezone.utc)
    return n.replace(hour=0, minute=0, second=0, microsecond=0)


def _extract_codes(text: str | None) -> list[str]:
    if not text:
        return []
    return [m.group(1) for m in _CODE_RE.finditer(text)]


async def build_medical_ontology_stats(db: AsyncSession) -> OntologyStatsResponse:
    start = _utc_today_floor()

    total = await db.scalar(
        select(func.count()).select_from(Diagnosis).where(Diagnosis.created_at >= start),
    ) or 0
    passed = await db.scalar(
        select(func.count())
        .select_from(Diagnosis)
        .where(Diagnosis.created_at >= start, Diagnosis.ontology_passed.is_(True)),
    ) or 0

    pr = (passed / total) if total else 1.0

    fail_rows = (
        (
            await db.execute(
                select(Diagnosis.report)
                .where(
                    Diagnosis.created_at >= start,
                    Diagnosis.ontology_passed.is_(False),
                )
                .limit(200),
            )
        )
        .scalars()
        .all()
    )

    code_counter: Counter[str] = Counter()
    for rep in fail_rows:
        codes = _extract_codes(rep)
        if codes:
            for c in codes:
                code_counter[c] += 1
        else:
            code_counter["ONT-MED-UNSPEC"] += 1

    top = [
        OntologyErrorBucket(code=c, count=n, message="최근 실패 진단 보고서에서 추출")
        for c, n in code_counter.most_common(8)
    ]

    now = datetime.now(timezone.utc).isoformat()
    slice_self = OntologyDomainSlice(
        domain="medical",
        today_validations=int(total),
        pass_rate=float(round(pr, 4)),
        top_errors=top,
    )
    return OntologyStatsResponse(
        domain="medical",
        today_validations=int(total),
        pass_rate=float(round(pr, 4)),
        top_errors=top,
        generated_at=now,
        service="medi-iot",
        domains_detail=[slice_self],
    )
