"""향후 모니터링을 위한 분리된 지표.

결정적 점수는 품질 소견과 관찰 행에 쓰지 않는다.
예측값은 만들지 않으며 측정값을 대체하지 않는다.
"""
from __future__ import annotations

import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.clinical_support import (
    ClinicalObservation,
    DataQualityFinding,
    DataQualityRule,
    StudySubject,
    StudyVisit,
)
from services.clinical_records import get_effective_observation


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
