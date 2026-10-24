"""향후 모니터링을 위한 분리된 지표.

결정적 점수는 품질 소견과 관찰 행에 쓰지 않는다.
예측값은 만들지 않으며 측정값을 대체하지 않는다.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.clinical_support import (
    ClinicalObservation,
    ClinicalQuery,
    DataQualityFinding,
    DataQualityRule,
    MonitoringIndicator,
    MonitoringIndicatorRun,
    StudySubject,
    StudyVisit,
    VisitWindow,
)
from services.clinical_readiness import latest_approved_protocol
from services.clinical_records import (
    _hash,
    _require_study_member,
    get_effective_observation,
)

INDICATOR_CODES = (
    "REPEATED_MISSING_OBSERVATION",
    "UNRESOLVED_QUERY_AGING",
    "RECURRENT_QUALITY_FINDING",
    "VISIT_SCHEDULING_DEVIATION",
    "UNUSUAL_CORRECTION_FREQUENCY",
    "INCONSISTENT_LONGITUDINAL_MEASUREMENT",
)
UNRESOLVED_QUERY_STATUSES = ("open", "answered", "reopened")


def completeness_score(session: Session, *, study_id: str) -> dict:
    rules = list(session.scalars(
        select(DataQualityRule).where(
            DataQualityRule.study_id == study_id,
            DataQualityRule.status == "active",
        )
    ).all())
    expected = 0
    present = 0
    visits = list(session.scalars(
        select(StudyVisit).join(StudyVisit.subject).where(StudyVisit.subject.has(study_id=study_id))
    ).all())
    for rule in rules:
        logic = json.loads(rule.logic_json)
        if logic.get("kind") != "required_effective":
            continue
        for visit in visits:
            expected += 1
            if get_effective_observation(session, visit_id=visit.id, code=logic["code"]) is not None:
                present += 1
    score = None if expected == 0 else present / expected
    return {
        "kind": "completeness",
        "status": "DETERMINISTIC",
        "score": score,
        "predicted_value": None,
    }


def reliability_indicator(session: Session, *, study_id: str) -> dict:
    findings = session.scalar(
        select(func.count()).select_from(DataQualityFinding).where(
            DataQualityFinding.study_id == study_id,
            DataQualityFinding.status == "open",
        )
    ) or 0
    observations = session.scalar(
        select(func.count())
        .select_from(ClinicalObservation)
        .join(StudyVisit, StudyVisit.id == ClinicalObservation.visit_id)
        .join(StudySubject, StudySubject.id == StudyVisit.subject_id)
        .where(StudySubject.study_id == study_id, ClinicalObservation.record_status == "final")
    ) or 0
    return {
        "kind": "reliability",
        "status": "DETERMINISTIC",
        "open_findings": int(findings),
        "final_observations": int(observations),
        "predicted_value": None,
    }


def deferred_prediction(kind: str) -> dict:
    if kind not in {
        "missing_data_risk",
        "visit_noncompliance",
        "measurement_anomaly",
        "study_completion",
    }:
        kind = "unspecified"
    return {"kind": kind, "status": "DEFERRED", "model": None, "predicted_value": None}


def compute_monitoring_indicators(
    session: Session,
    *,
    study_id: str,
    actor_user_id: str,
) -> list[MonitoringIndicator]:
    """결정적 지표만 추가한다. 원본 관찰과 질의를 바꾸지 않는다."""
    _require_study_member(session, study_id, actor_user_id)
    protocol = latest_approved_protocol(session, study_id)
    requirements = {} if protocol is None else json.loads(protocol.requirements_json)
    run = MonitoringIndicatorRun(
        study_id=study_id,
        protocol_definition_id=None if protocol is None else protocol.id,
        actor_user_id=actor_user_id,
        computed_at=datetime.now(timezone.utc),
    )
    session.add(run)
    session.flush()
    created: list[MonitoringIndicator] = []
    for code in INDICATOR_CODES:
        if protocol is None:
            status, evidence = "BLOCKED_PENDING_PROTOCOL", {"reason": "approved_protocol_missing"}
        else:
            status, evidence = _INDICATORS[code](session, study_id, requirements)
        evidence = {
            **evidence,
            "predicted_value": None,
            "efficacy_claim": None,
            "automatic_clinical_mutation": False,
        }
        row = MonitoringIndicator(
            run_id=run.id,
            study_id=study_id,
            indicator_code=code,
            status=status,
            evidence_json=json.dumps(evidence, sort_keys=True, default=str),
            content_hash=_hash({"code": code, "status": status, "evidence": evidence}),
            computed_at=run.computed_at,
        )
        session.add(row)
        created.append(row)
    session.flush()
    return created


def ai_monitoring_handoff(indicator: MonitoringIndicator) -> dict:
    """AI 모니터링, 위험 평가, 사람 검토, 임상 조치로 이어지는 미래 경계."""
    return {
        "interface": ["AI_MONITORING", "RISK_ASSESSMENT", "HUMAN_REVIEW", "CLINICAL_ACTION"],
        "indicator_id": indicator.id,
        "indicator_code": indicator.indicator_code,
        "indicator_status": indicator.status,
        "automatic_clinical_mutation": False,
        "prediction": None,
        "efficacy_claim": None,
        "status": "FOUNDATION_ONLY",
    }


def _store_signal(items: list[dict]) -> tuple[str, dict]:
    if not items:
        return "CLEAR", {"count": 0, "items": []}
    return "OPEN", {"count": len(items), "items": items}


def _repeated_missing(session: Session, study_id: str, requirements: dict) -> tuple[str, dict]:
    required = requirements.get("required_observations") or []
    if not required:
        return "NOT_CONFIGURED", {"reason": "required_observations_missing"}
    subjects = list(session.scalars(select(StudySubject).where(StudySubject.study_id == study_id)).all())
    found: list[dict] = []
    for subject in subjects:
        visits = list(session.scalars(select(StudyVisit).where(StudyVisit.subject_id == subject.id)).all())
        for spec in required:
            code = str(spec["code"])
            missing = [
                visit.id for visit in visits
                if get_effective_observation(
                    session, visit_id=visit.id, code=code,
                    laterality=str(spec.get("laterality", "NA")),
                    method=str(spec.get("method", "NA")),
                    repeat_index=int(spec.get("repeat_index", 1)),
                ) is None
            ]
            if len(missing) >= 2:
                found.append({"subject_id": subject.id, "code": code, "visit_ids": missing})
    return _store_signal(found)


def _query_aging(session: Session, study_id: str, requirements: dict) -> tuple[str, dict]:
    days = requirements.get("query_aging_days")
    if not isinstance(days, int):
        return "NOT_CONFIGURED", {"reason": "query_aging_days_missing"}
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = list(session.scalars(
        select(ClinicalQuery).where(
            ClinicalQuery.study_id == study_id,
            ClinicalQuery.status.in_(UNRESOLVED_QUERY_STATUSES),
        )
    ).all())
    aged = []
    for row in rows:
        opened = row.opened_at
        if opened is not None and opened.tzinfo is None:
            opened = opened.replace(tzinfo=timezone.utc)
        if opened is not None and opened <= cutoff:
            aged.append({"query_id": row.id, "status": row.status, "opened_at": opened.isoformat()})
    return _store_signal(aged)


def _recurrent_findings(session: Session, study_id: str, requirements: dict) -> tuple[str, dict]:
    minimum = requirements.get("recurrent_finding_min")
    if not isinstance(minimum, int):
        return "NOT_CONFIGURED", {"reason": "recurrent_finding_min_missing"}
    rows = list(session.scalars(
        select(DataQualityFinding).where(
            DataQualityFinding.study_id == study_id,
            DataQualityFinding.status == "open",
        )
    ).all())
    grouped: dict[str, list[str]] = {}
    for row in rows:
        grouped.setdefault(row.rule_id, []).append(row.id)
    found = [
        {"rule_id": rule_id, "finding_ids": ids}
        for rule_id, ids in grouped.items()
        if len(ids) >= minimum
    ]
    return _store_signal(found)


def _visit_deviation(session: Session, study_id: str, requirements: dict) -> tuple[str, dict]:
    del requirements
    visits = list(session.scalars(
        select(StudyVisit).join(StudyVisit.subject).where(StudyVisit.subject.has(study_id=study_id))
    ).all())
    comparable = [visit for visit in visits if visit.window_id and visit.subject.enrolled_on]
    if not comparable:
        return "NOT_CONFIGURED", {"reason": "visit_window_missing"}
    found = []
    for visit in comparable:
        window = session.get(VisitWindow, visit.window_id)
        enrolled = visit.subject.enrolled_on
        if window is None or enrolled is None:
            continue
        anchor = enrolled + timedelta(days=window.target_day)
        low = anchor - timedelta(days=window.minus_days)
        high = anchor + timedelta(days=window.plus_days)
        if visit.occurred_on < low or visit.occurred_on > high:
            found.append({
                "visit_id": visit.id,
                "occurred_on": visit.occurred_on.isoformat(),
                "window_id": window.id,
            })
    return _store_signal(found)


def _correction_frequency(session: Session, study_id: str, requirements: dict) -> tuple[str, dict]:
    minimum = requirements.get("correction_frequency_min")
    if not isinstance(minimum, int):
        return "NOT_CONFIGURED", {"reason": "correction_frequency_min_missing"}
    rows = list(session.scalars(
        select(ClinicalObservation)
        .join(StudyVisit, StudyVisit.id == ClinicalObservation.visit_id)
        .join(StudySubject, StudySubject.id == StudyVisit.subject_id)
        .where(StudySubject.study_id == study_id, ClinicalObservation.revision >= minimum)
    ).all())
    return _store_signal([
        {"observation_id": row.id, "revision": row.revision, "visit_id": row.visit_id}
        for row in rows
    ])


def _longitudinal(session: Session, study_id: str, requirements: dict) -> tuple[str, dict]:
    limits = requirements.get("longitudinal_max_abs_delta")
    if not isinstance(limits, dict) or not limits:
        return "NOT_CONFIGURED", {"reason": "longitudinal_max_abs_delta_missing"}
    subjects = list(session.scalars(select(StudySubject).where(StudySubject.study_id == study_id)).all())
    found = []
    for subject in subjects:
        visits = list(session.scalars(
            select(StudyVisit)
            .where(StudyVisit.subject_id == subject.id)
            .order_by(StudyVisit.occurred_on, StudyVisit.visit_code)
        ).all())
        for code, limit in limits.items():
            values = []
            for visit in visits:
                effective = get_effective_observation(session, visit_id=visit.id, code=str(code))
                if effective is not None and effective.value_number is not None:
                    values.append((visit.id, effective.id, float(effective.value_number)))
            for previous, current in zip(values, values[1:]):
                delta = abs(current[2] - previous[2])
                if delta > float(limit):
                    found.append({
                        "subject_id": subject.id,
                        "code": str(code),
                        "previous_observation_id": previous[1],
                        "current_observation_id": current[1],
                        "delta": delta,
                    })
    return _store_signal(found)


_INDICATORS = {
    "REPEATED_MISSING_OBSERVATION": _repeated_missing,
    "UNRESOLVED_QUERY_AGING": _query_aging,
    "RECURRENT_QUALITY_FINDING": _recurrent_findings,
    "VISIT_SCHEDULING_DEVIATION": _visit_deviation,
    "UNUSUAL_CORRECTION_FREQUENCY": _correction_frequency,
    "INCONSISTENT_LONGITUDINAL_MEASUREMENT": _longitudinal,
}


def list_monitoring_indicators(
    session: Session, *, study_id: str, actor_user_id: str,
) -> list[MonitoringIndicator]:
    _require_study_member(session, study_id, actor_user_id)
    return list(session.scalars(
        select(MonitoringIndicator)
        .where(MonitoringIndicator.study_id == study_id)
        .order_by(MonitoringIndicator.computed_at, MonitoringIndicator.indicator_code)
    ).all())
