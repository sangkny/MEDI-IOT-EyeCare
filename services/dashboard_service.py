"""관리자 대시보드 통계 계산 로직."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone, date
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.medical import (
    Diagnosis,
    DiagnosisSeverityEnum,
    EyeExam,
    Patient,
)
from schemas.dashboard import (
    DashboardAlert,
    DashboardAlertsResponse,
    DashboardStatsResponse,
    DashboardLLMUsageResponse,
    ProviderUsageRow,
    DiagnosisBucket,
    ExamIcdAgreementStats,
)
from services.llm_telemetry import get_daily_llm_usage
from services.trend_analyzer import TrendAnalyzer

log = logging.getLogger("services.dashboard")


def _utc_today_floor() -> datetime:
    """UTC 자정 경계일."""
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _diag_bucket(
    code: str | None,
    name: str | None,
    severity: DiagnosisSeverityEnum | None = None,
) -> tuple[str, str]:
    """(key, 한글 라벨)"""
    nm = name or ""
    c = (code or "").strip().upper()

    if severity == DiagnosisSeverityEnum.NORMAL or "정상" in nm:
        return "normal", "정상"
    if c in {"Z01.1"}:
        return "normal", "정상"

    if c.startswith("H36") or c.startswith("H35.0"):
        return "diabetic_retinopathy", "당뇨망막병증"
    if c.startswith("H35"):
        return "macular", "황반변성 및 기타 황반/망막"
    if c.startswith("H40"):
        return "glaucoma", "녹내장"
    return "other", "기타/미분류"


async def load_dashboard_stats(db: AsyncSession) -> DashboardStatsResponse:
    cutoff = _utc_today_floor()
    since_30d = cutoff - timedelta(days=30)

    exams_today = await db.scalar(
        select(func.count())
        .select_from(EyeExam)
        .where(EyeExam.created_at >= cutoff),
    )

    patients_today = await db.scalar(
        select(func.count())
        .select_from(Patient)
        .where(Patient.created_at >= cutoff),
    )

    recent_diags = (
        (
            await db.execute(
                select(
                    Diagnosis.diagnosis_code,
                    Diagnosis.diagnosis_name,
                    Diagnosis.severity,
                ).where(
                    Diagnosis.created_at >= since_30d,
                ),
            )
        )
        .tuples()
        .all()
    )

    buckets: dict[str, tuple[str, int]] = {}
    for code, nm, sev in recent_diags:
        key, label = _diag_bucket(code, nm, sev)
        if key not in buckets:
            buckets[key] = (label, 0)
        label2, cnt = buckets[key]
        buckets[key] = (label2, cnt + 1)

    order_keys = ["diabetic_retinopathy", "macular", "glaucoma", "normal", "other"]
    diag_out = []
    seen = set()
    for key in order_keys:
        seen.add(key)
        if key in buckets:
            label_kr, count = buckets[key]
            diag_out.append(DiagnosisBucket(key=key, label_kr=label_kr, count=count))
    for k, (label_kr, count) in sorted(buckets.items()):
        if k in seen:
            continue
        diag_out.append(DiagnosisBucket(key=k, label_kr=label_kr, count=count))

    # 검사 ICD vs AI 진단 ICD 일치
    agree_rows = (
        (
            await db.execute(
                select(EyeExam.icd_code, Diagnosis.diagnosis_code)
                .join(Diagnosis, Diagnosis.exam_id == EyeExam.id)
                .where(
                    and_(
                        EyeExam.icd_code.is_not(None),
                        EyeExam.icd_code != "",
                    ),
                ),
            )
        )
        .all()
    )
    compared = matched = 0
    for ex_icd, ai_icd in agree_rows:
        if not ai_icd or not ex_icd:
            continue
        compared += 1
        if str(ex_icd).strip().upper() == str(ai_icd).strip().upper():
            matched += 1

    rate = (matched / compared) if compared else None

    return DashboardStatsResponse(
        stats_date_local_utc=cutoff.date().isoformat(),
        exams_today=int(exams_today or 0),
        new_patients_today=int(patients_today or 0),
        diagnosis_buckets=diag_out,
        ai_icd_agreement_vs_exam=ExamIcdAgreementStats(
            compared_pairs=int(compared),
            matched_pairs=int(matched),
            agreement_rate=float(round(rate, 4)) if rate is not None else None,
            note=(
                "AI diagnosis_code 와 해당 검사 eye_exams.icd_code 문자열 동일 여부입니다. "
                "의사 최종 판별 필드는 추후 저장 시 별도 KPI로 교체 가능합니다."
            ),
        ),
    )


async def _patient_pairs_for_recent_high_risk(
    db: AsyncSession,
    since: datetime,
) -> list[tuple[str, str]]:
    """(patient_uuid, patient_code) 목록 중복 없이."""
    q = (
        select(Patient.id, Patient.patient_code)
        .join(EyeExam, EyeExam.patient_id == Patient.id)
        .join(Diagnosis, Diagnosis.exam_id == EyeExam.id)
        .where(
            and_(Diagnosis.created_at >= since, Patient.is_active.is_(True)),
        )
        .distinct()
    )
    rows = (await db.execute(q)).all()
    return [(r[0], r[1]) for r in rows]


async def load_dashboard_alerts(db: AsyncSession) -> DashboardAlertsResponse:
    now = datetime.now(timezone.utc)
    since_diag = now - timedelta(days=30)

    ontology_rows = (
        (
            await db.execute(
                select(
                    Patient.id,
                    Patient.patient_code,
                    Diagnosis.id,
                    Diagnosis.created_at,
                )
                .join(EyeExam, EyeExam.patient_id == Patient.id)
                .join(Diagnosis, Diagnosis.exam_id == EyeExam.id)
                .where(
                    and_(
                        Diagnosis.ontology_passed.is_(False),
                        Patient.is_active.is_(True),
                    ),
                    Diagnosis.created_at >= since_diag,
                )
                .order_by(Diagnosis.created_at.desc())
                .limit(50),
            )
        )
        .all()
    )
    ontology_alerts = [
        DashboardAlert(
            patient_id=pid,
            patient_code=pcode,
            reason="OntologyValidator 미통과 AI 진단 (의사 검토 필요)",
            severity="warning",
        )
        for pid, pcode, _did, _at in ontology_rows
    ]

    analyzer = TrendAnalyzer(db)
    patient_scope = await _patient_pairs_for_recent_high_risk(db, since_diag)
    if len(patient_scope) > 35:
        patient_scope = patient_scope[:35]

    urgent: dict[str, DashboardAlert] = {}
    for pid, pcode in patient_scope:
        summary = await analyzer.analyze(pid, limit=12)
        if summary.overall_status == "worsening" or summary.alerts:
            urgent[pid] = DashboardAlert(
                patient_id=pid,
                patient_code=pcode,
                reason="; ".join(summary.alerts[:3]) or "시력 또는 안압 추이 위험",
                severity="urgent",
            )

    urgent_list = list(urgent.values())

    seen_ont: dict[str, DashboardAlert] = {}
    for alert in ontology_alerts:
        seen_ont.setdefault(alert.patient_id, alert)
    ontology_alerts_trimmed = list(seen_ont.values())[:25]

    return DashboardAlertsResponse(
        generated_at=now,
        urgent_tracking=urgent_list[:40],
        ontology_validator_warnings=ontology_alerts_trimmed,
    )


async def load_llm_dashboard() -> DashboardLLMUsageResponse:
    raw = await get_daily_llm_usage()
    by_provider = [
        ProviderUsageRow(
            provider_key=row["provider_key"],
            calls_today=int(row["calls_today"]),
            estimated_tokens_today=int(row["estimated_tokens"]),
        )
        for row in raw["by_provider"]
    ]
    d = date.fromisoformat(str(raw["date"]))
    return DashboardLLMUsageResponse(
        date=d,
        calls_today=int(raw["calls_today"]),
        total_tokens_estimated=int(raw["total_tokens_estimated"]),
        by_provider=by_provider,
        aggregation_note=str(raw.get("aggregation_note", "")),
    )
