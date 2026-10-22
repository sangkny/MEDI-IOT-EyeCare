"""규칙 기반 품질 검사. 관찰 값은 바꾸지 않고 finding 만 추가한다."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.clinical_support import (
    ClinicalObservation,
    DataQualityFinding,
    DataQualityRule,
    QuestionnaireDefinition,
    QuestionnaireResponse,
    StudyVisit,
)
from services.clinical_records import (
    ClinicalRecordError,
    _hash,
    get_effective_observation,
    record_quality_finding,
)


def run_quality_rules(session: Session, *, study_id: str, actor_user_id: str) -> list[DataQualityFinding]:
    rules = list(session.scalars(
        select(DataQualityRule).where(
            DataQualityRule.study_id == study_id,
            DataQualityRule.status == "active",
        )
    ).all())
    created: list[DataQualityFinding] = []
    for rule in rules:
        logic = json.loads(rule.logic_json)
        kind = logic.get("kind")
        if kind == "numeric_range":
            created.extend(_numeric_range(session, rule, logic, actor_user_id))
        elif kind == "required_effective":
            created.extend(_required_effective(session, rule, logic, actor_user_id))
        elif kind == "max_finals":
            created.extend(_max_finals(session, rule, logic, actor_user_id))
        elif kind == "questionnaire_complete":
            created.extend(_questionnaire_complete(session, rule, logic, actor_user_id))
        elif kind == "revision_chain":
            created.extend(_revision_chain(session, rule, actor_user_id))
        elif kind == "provenance":
            created.extend(_provenance(session, rule, actor_user_id))
        else:
            raise ClinicalRecordError("지원하지 않는 품질 규칙입니다.")
    return created


def review_finding(
    session: Session,
    finding_id: str,
    *,
    actor_user_id: str,
    reason: str,
) -> DataQualityFinding:
    finding = session.get(DataQualityFinding, finding_id)
    if finding is None:
        raise ClinicalRecordError("품질 소견이 없습니다.")
    if not reason or not reason.strip():
        raise ClinicalRecordError("검토 사유가 필요합니다.")
    observation = session.get(ClinicalObservation, finding.target_id)
    before = None if observation is None else (observation.value_number, observation.row_hash)
    finding.status = "reviewed"
    finding.waive_reason = reason.strip()
    finding.closed_by = actor_user_id
    finding.closed_at = datetime.now(timezone.utc)
    session.flush()
    if observation is not None:
        session.refresh(observation)
        if (observation.value_number, observation.row_hash) != before:
            raise ClinicalRecordError("품질 검토가 관찰 값을 바꿨습니다.")
    return finding


def _open_or_create(
    session: Session,
    rule: DataQualityRule,
    *,
    actor_user_id: str,
    target_type: str,
    target_id: str,
    message_code: str,
    visit_id: str | None = None,
    subject_id: str | None = None,
) -> DataQualityFinding | None:
    fingerprint = _hash({
        "rule_id": rule.id,
        "rule_version": rule.version_number,
        "target_id": target_id,
        "message_code": message_code,
    })
    existing = session.scalar(
        select(DataQualityFinding).where(
            DataQualityFinding.fingerprint == fingerprint,
            DataQualityFinding.status.in_(("open", "reviewed")),
        )
    )
    if existing is not None:
        return None
    return record_quality_finding(
        session,
        rule_id=rule.id,
        study_id=rule.study_id,
        target_type=target_type,
        target_id=target_id,
        fingerprint=fingerprint,
        message_code=message_code,
        actor_user_id=actor_user_id,
        subject_id=subject_id,
        visit_id=visit_id,
    )


def _visits(session: Session, study_id: str) -> list[StudyVisit]:
    stmt = select(StudyVisit).join(StudyVisit.subject).where(StudyVisit.subject.has(study_id=study_id))
    return list(session.scalars(stmt).all())


def _numeric_range(session, rule, logic, actor_user_id):
    found = []
    code = logic["code"]
    for visit in _visits(session, rule.study_id):
        for row in visit.observations:
            if row.code != code or row.record_status != "final":
                continue
            if row.value_number is None:
                continue
            value = float(row.value_number)
            if value < float(logic["min"]) or value > float(logic["max"]):
                created = _open_or_create(
                    session, rule, actor_user_id=actor_user_id,
                    target_type="observation", target_id=row.id,
                    message_code="numeric_range", visit_id=visit.id,
                    subject_id=visit.subject_id,
                )
                if created is not None:
                    found.append(created)
    return found


def _required_effective(session, rule, logic, actor_user_id):
    found = []
    code = logic["code"]
    for visit in _visits(session, rule.study_id):
        current = get_effective_observation(session, visit_id=visit.id, code=code)
        if current is None:
            created = _open_or_create(
                session, rule, actor_user_id=actor_user_id,
                target_type="visit", target_id=visit.id,
                message_code="required_effective", visit_id=visit.id,
                subject_id=visit.subject_id,
            )
            if created is not None:
                found.append(created)
    return found


def _max_finals(session, rule, logic, actor_user_id):
    found = []
    code = logic["code"]
    limit = int(logic["max"])
    for visit in _visits(session, rule.study_id):
        keys = {
            (row.laterality, row.method, row.repeat_index)
            for row in visit.observations
            if row.code == code and row.record_status == "final"
        }
        if len(keys) > limit:
            created = _open_or_create(
                session, rule, actor_user_id=actor_user_id,
                target_type="visit", target_id=visit.id,
                message_code="max_finals", visit_id=visit.id,
                subject_id=visit.subject_id,
            )
            if created is not None:
                found.append(created)
    return found


def _questionnaire_complete(session, rule, logic, actor_user_id):
    found = []
    definition = session.scalar(
        select(QuestionnaireDefinition).where(
            QuestionnaireDefinition.study_id == rule.study_id,
            QuestionnaireDefinition.code == logic["definition_code"],
        )
    )
    if definition is None:
        return found
    version_ids = {version.id for version in definition.versions}
    for visit in _visits(session, rule.study_id):
        finals = [
            row for row in visit.responses
            if row.status == "final" and row.version_id in version_ids
        ]
        if not finals:
            created = _open_or_create(
                session, rule, actor_user_id=actor_user_id,
                target_type="visit", target_id=visit.id,
                message_code="questionnaire_complete", visit_id=visit.id,
                subject_id=visit.subject_id,
            )
            if created is not None:
                found.append(created)
    return found


def _revision_chain(session, rule, actor_user_id):
    found = []
    for visit in _visits(session, rule.study_id):
        by_id = {row.id: row for row in visit.observations}
        for row in visit.observations:
            if row.supersedes_observation_id is None:
                continue
            prior = by_id.get(row.supersedes_observation_id)
            if prior is None or row.revision != prior.revision + 1:
                created = _open_or_create(
                    session, rule, actor_user_id=actor_user_id,
                    target_type="observation", target_id=row.id,
                    message_code="revision_chain", visit_id=visit.id,
                    subject_id=visit.subject_id,
                )
                if created is not None:
                    found.append(created)
    return found


def _provenance(session, rule, actor_user_id):
    found = []
    for visit in _visits(session, rule.study_id):
        for row in visit.observations:
            if row.record_status == "final" and (not row.recorded_by or row.finalized_by is None):
                created = _open_or_create(
                    session, rule, actor_user_id=actor_user_id,
                    target_type="observation", target_id=row.id,
                    message_code="provenance", visit_id=visit.id,
                    subject_id=visit.subject_id,
                )
                if created is not None:
                    found.append(created)
    return found
