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
    QualityEvaluationRun,
    QuestionnaireDefinition,
    QuestionnaireResponse,
    StudySubject,
    StudyVisit,
    VisitFormAssignment,
)
from services.clinical_records import (
    ClinicalRecordError,
    _hash,
    get_effective_observation,
    record_quality_finding,
)


def run_quality_rules(
    session: Session,
    *,
    study_id: str,
    actor_user_id: str,
    scope: str = "study",
    scope_id: str | None = None,
    trigger: str = "manual",
) -> list[DataQualityFinding]:
    if scope not in {"study", "subject", "visit", "form"}:
        raise ClinicalRecordError("지원하지 않는 검증 범위입니다.")
    if scope != "study" and not scope_id:
        raise ClinicalRecordError("검증 범위 식별자가 필요합니다.")
    context_id = study_id if scope == "study" else scope_id
    run = QualityEvaluationRun(
        study_id=study_id,
        scope=scope,
        scope_id=context_id,
        trigger=trigger,
        status="running",
        actor_user_id=actor_user_id,
        finding_count=0,
        started_at=datetime.now(timezone.utc),
    )
    session.add(run)
    session.flush()
    try:
        rules = list(session.scalars(
            select(DataQualityRule).where(
                DataQualityRule.study_id == study_id,
                DataQualityRule.status == "active",
            )
        ).all())
        created: list[DataQualityFinding] = []
        visits = _scoped_visits(session, study_id, scope, context_id)
        for rule in rules:
            logic = json.loads(rule.logic_json)
            kind = logic.get("kind")
            if kind == "blocked_source":
                continue
            handler = _HANDLERS.get(kind)
            if handler is None:
                raise ClinicalRecordError("지원하지 않는 품질 규칙입니다.")
            created.extend(handler(
                session, rule, logic, actor_user_id, visits, scope, context_id,
            ))
        run.status = "completed"
        run.finding_count = len(created)
        run.finished_at = datetime.now(timezone.utc)
        session.flush()
        return created
    except Exception:
        run.status = "failed"
        run.finished_at = datetime.now(timezone.utc)
        session.flush()
        raise


def validate_after_entry(
    session: Session, *, visit_id: str, actor_user_id: str,
) -> list[DataQualityFinding]:
    visit = session.get(StudyVisit, visit_id)
    if visit is None:
        raise ClinicalRecordError("Visit 가 없습니다.")
    from services.clinical_records import _require_site_member
    _require_site_member(session, visit.subject.site_id, actor_user_id)
    return run_quality_rules(
        session,
        study_id=visit.subject.study_id,
        actor_user_id=actor_user_id,
        scope="visit",
        scope_id=visit_id,
        trigger="entry",
    )


def medi_des_001_rule_catalog() -> list[dict]:
    """승인된 프로토콜이 없으므로 임계값과 Visit 정의는 만들지 않는다."""
    return [
        {
            "code": "TBUT_PRESENT",
            "version_number": 1,
            "severity": "error",
            "source_status": "SYNTHETIC_DEMONSTRATION",
            "logic": {"kind": "required_effective", "code": "TBUT"},
        },
        {
            "code": "SCHIRMER_PRESENT",
            "version_number": 1,
            "severity": "error",
            "source_status": "SYNTHETIC_DEMONSTRATION",
            "logic": {"kind": "required_effective", "code": "SCHIRMER"},
        },
        {
            "code": "OSDI_PRESENT",
            "version_number": 1,
            "severity": "error",
            "source_status": "SYNTHETIC_DEMONSTRATION",
            "logic": {"kind": "questionnaire_complete", "definition_code": "OSDI"},
        },
        {
            "code": "VISIT_TIMING",
            "version_number": 1,
            "severity": "warning",
            "source_status": "BLOCKED_PENDING_SOURCE",
            "logic": {"kind": "blocked_source", "topic": "visit_timing"},
        },
        {
            "code": "TREATMENT_ADHERENCE",
            "version_number": 1,
            "severity": "warning",
            "source_status": "BLOCKED_PENDING_SOURCE",
            "logic": {"kind": "blocked_source", "topic": "treatment_adherence"},
        },
        {
            "code": "MISSING_FOLLOW_UP",
            "version_number": 1,
            "severity": "warning",
            "source_status": "BLOCKED_PENDING_SOURCE",
            "logic": {"kind": "blocked_source", "topic": "missing_follow_up"},
        },
        {
            "code": "PROTOCOL_DEVIATION",
            "version_number": 1,
            "severity": "warning",
            "source_status": "BLOCKED_PENDING_SOURCE",
            "logic": {"kind": "blocked_source", "topic": "protocol_deviation"},
        },
    ]


def register_demonstration_rules(session: Session, *, study_id: str) -> list[DataQualityRule]:
    from services.clinical_records import add_quality_rule
    created: list[DataQualityRule] = []
    for item in medi_des_001_rule_catalog():
        if item["source_status"] != "SYNTHETIC_DEMONSTRATION":
            continue
        if any(key in item["logic"] for key in ("min", "max", "threshold")):
            raise ClinicalRecordError("확인되지 않은 임상 임계값은 등록하지 않습니다.")
        created.append(add_quality_rule(
            session,
            study_id=study_id,
            code=item["code"],
            version_number=item["version_number"],
            severity=item["severity"],
            logic_json=json.dumps(item["logic"], sort_keys=True),
        ))
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
    source_revision: int | None = None,
    evaluation_scope: str = "study",
    evaluation_scope_id: str | None = None,
) -> DataQualityFinding | None:
    fingerprint = _hash({
        "rule_id": rule.id,
        "rule_version": rule.version_number,
        "target_id": target_id,
        "message_code": message_code,
        "source_revision": source_revision,
        "evaluation_scope": evaluation_scope,
        "evaluation_scope_id": evaluation_scope_id,
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
        source_revision=source_revision,
        evaluation_scope=evaluation_scope,
        evaluation_scope_id=evaluation_scope_id,
    )


def _visits(session: Session, study_id: str) -> list[StudyVisit]:
    stmt = select(StudyVisit).join(StudyVisit.subject).where(StudyVisit.subject.has(study_id=study_id))
    return list(session.scalars(stmt).all())


def _scoped_visits(session: Session, study_id: str, scope: str, scope_id: str | None) -> list[StudyVisit]:
    visits = _visits(session, study_id)
    if scope == "study":
        return visits
    if scope == "subject":
        return [visit for visit in visits if visit.subject_id == scope_id]
    if scope == "visit":
        matched = [visit for visit in visits if visit.id == scope_id]
        if not matched:
            raise ClinicalRecordError("Visit 가 이 연구에 없습니다.")
        return matched
    codes = set(session.scalars(
        select(VisitFormAssignment.visit_code).where(
            VisitFormAssignment.study_id == study_id,
            VisitFormAssignment.definition_id == scope_id,
        )
    ).all())
    if not codes:
        raise ClinicalRecordError("폼 배정이 이 연구에 없습니다.")
    return [visit for visit in visits if visit.visit_code in codes]


def _context(scope: str, scope_id: str | None) -> dict:
    return {"evaluation_scope": scope, "evaluation_scope_id": scope_id}


def _numeric_range(session, rule, logic, actor_user_id, visits, scope, scope_id):
    found = []
    code = logic["code"]
    context = _context(scope, scope_id)
    for visit in visits:
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
                    subject_id=visit.subject_id, source_revision=row.revision,
                    **context,
                )
                if created is not None:
                    found.append(created)
    return found


def _required_effective(session, rule, logic, actor_user_id, visits, scope, scope_id):
    found = []
    code = logic["code"]
    context = _context(scope, scope_id)
    for visit in visits:
        current = get_effective_observation(session, visit_id=visit.id, code=code)
        if current is None:
            created = _open_or_create(
                session, rule, actor_user_id=actor_user_id,
                target_type="visit", target_id=visit.id,
                message_code="required_effective", visit_id=visit.id,
                subject_id=visit.subject_id, **context,
            )
            if created is not None:
                found.append(created)
    return found


def _missing_value(session, rule, logic, actor_user_id, visits, scope, scope_id):
    found = []
    code = logic["code"]
    context = _context(scope, scope_id)
    for visit in visits:
        current = get_effective_observation(session, visit_id=visit.id, code=code)
        if current is None:
            continue
        blank_text = not (current.value_text and current.value_text.strip())
        if current.value_number is None and blank_text:
            created = _open_or_create(
                session, rule, actor_user_id=actor_user_id,
                target_type="observation", target_id=current.id,
                message_code="missing_value", visit_id=visit.id,
                subject_id=visit.subject_id, source_revision=current.revision,
                **context,
            )
            if created is not None:
                found.append(created)
    return found


def _max_finals(session, rule, logic, actor_user_id, visits, scope, scope_id):
    found = []
    code = logic["code"]
    limit = int(logic["max"])
    context = _context(scope, scope_id)
    for visit in visits:
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
                subject_id=visit.subject_id, **context,
            )
            if created is not None:
                found.append(created)
    return found


def _duplicate_observation(session, rule, logic, actor_user_id, visits, scope, scope_id):
    found = []
    code = logic.get("code")
    context = _context(scope, scope_id)
    for visit in visits:
        groups: dict[tuple, list[ClinicalObservation]] = {}
        for row in visit.observations:
            if row.record_status != "final":
                continue
            if code and row.code != code:
                continue
            key = (row.code, row.laterality, row.method, row.repeat_index)
            groups.setdefault(key, []).append(row)
        for rows in groups.values():
            if len(rows) > 1 and not _single_revision_chain(rows):
                latest = max(rows, key=lambda item: item.revision)
                created = _open_or_create(
                    session, rule, actor_user_id=actor_user_id,
                    target_type="observation", target_id=latest.id,
                    message_code="duplicate_observation", visit_id=visit.id,
                    subject_id=visit.subject_id, source_revision=latest.revision,
                    **context,
                )
                if created is not None:
                    found.append(created)
    return found


def _single_revision_chain(rows: list[ClinicalObservation]) -> bool:
    ordered = sorted(rows, key=lambda row: row.revision)
    for index, row in enumerate(ordered):
        if index == 0:
            if row.supersedes_observation_id is not None:
                return False
            continue
        prior = ordered[index - 1]
        if row.supersedes_observation_id != prior.id or row.revision != prior.revision + 1:
            return False
    return True


def _visit_date_order(session, rule, logic, actor_user_id, visits, scope, scope_id):
    found = []
    order = list(logic.get("order") or [])
    if len(order) < 2:
        raise ClinicalRecordError("Visit 순서 규칙에는 두 개 이상의 코드가 필요합니다.")
    context = _context(scope, scope_id)
    by_subject: dict[str, list[StudyVisit]] = {}
    for visit in visits:
        by_subject.setdefault(visit.subject_id, []).append(visit)
    for subject_id, subject_visits in by_subject.items():
        dated: list[StudyVisit] = []
        for code in order:
            matches = [visit for visit in subject_visits if visit.visit_code == code]
            if len(matches) != 1:
                dated = []
                break
            dated.append(matches[0])
        for previous, nxt in zip(dated, dated[1:]):
            if nxt.occurred_on < previous.occurred_on:
                created = _open_or_create(
                    session, rule, actor_user_id=actor_user_id,
                    target_type="visit", target_id=nxt.id,
                    message_code="visit_date_order", visit_id=nxt.id,
                    subject_id=subject_id, **context,
                )
                if created is not None:
                    found.append(created)
    return found


def _questionnaire_complete(session, rule, logic, actor_user_id, visits, scope, scope_id):
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
    context = _context(scope, scope_id)
    for visit in visits:
        finals = [
            row for row in visit.responses
            if row.status == "final" and row.version_id in version_ids
        ]
        if not finals:
            created = _open_or_create(
                session, rule, actor_user_id=actor_user_id,
                target_type="visit", target_id=visit.id,
                message_code="questionnaire_complete", visit_id=visit.id,
                subject_id=visit.subject_id, **context,
            )
            if created is not None:
                found.append(created)
    return found


def _questionnaire_incomplete(session, rule, logic, actor_user_id, visits, scope, scope_id):
    from services.clinical_records import response_errors
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
    context = _context(scope, scope_id)
    for visit in visits:
        for response in visit.responses:
            if response.version_id not in version_ids:
                continue
            incomplete = response.status != "final" or bool(response_errors(session, response))
            if incomplete:
                created = _open_or_create(
                    session, rule, actor_user_id=actor_user_id,
                    target_type="questionnaire_response", target_id=response.id,
                    message_code="questionnaire_incomplete", visit_id=visit.id,
                    subject_id=visit.subject_id, **context,
                )
                if created is not None:
                    found.append(created)
    return found


def _revision_chain(session, rule, logic, actor_user_id, visits, scope, scope_id):
    found = []
    context = _context(scope, scope_id)
    for visit in visits:
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
                    subject_id=visit.subject_id, source_revision=row.revision,
                    **context,
                )
                if created is not None:
                    found.append(created)
    return found


def _provenance(session, rule, logic, actor_user_id, visits, scope, scope_id):
    found = []
    context = _context(scope, scope_id)
    for visit in visits:
        for row in visit.observations:
            if row.record_status == "final" and (not row.recorded_by or row.finalized_by is None):
                created = _open_or_create(
                    session, rule, actor_user_id=actor_user_id,
                    target_type="observation", target_id=row.id,
                    message_code="provenance", visit_id=visit.id,
                    subject_id=visit.subject_id, source_revision=row.revision,
                    **context,
                )
                if created is not None:
                    found.append(created)
    return found


def _cross_field(session, rule, logic, actor_user_id, visits, scope, scope_id):
    relation = logic.get("relation")
    if relation != "lte":
        raise ClinicalRecordError("지원하지 않는 교차 항목 관계입니다.")
    found = []
    context = _context(scope, scope_id)
    for visit in visits:
        left = get_effective_observation(session, visit_id=visit.id, code=logic["left_code"])
        right = get_effective_observation(session, visit_id=visit.id, code=logic["right_code"])
        if left is None or right is None or left.value_number is None or right.value_number is None:
            continue
        if float(left.value_number) > float(right.value_number):
            created = _open_or_create(
                session, rule, actor_user_id=actor_user_id,
                target_type="visit", target_id=visit.id,
                message_code="cross_field", visit_id=visit.id,
                subject_id=visit.subject_id, **context,
            )
            if created is not None:
                found.append(created)
    return found


def list_quality_findings(
    session: Session,
    *,
    study_id: str,
    actor_user_id: str,
    status: str | None = None,
    severity: str | None = None,
) -> list[DataQualityFinding]:
    from services.clinical_records import _require_study_member, list_sites_for_member
    _require_study_member(session, study_id, actor_user_id)
    site_ids = {site.id for site in list_sites_for_member(session, study_id, actor_user_id)}
    stmt = select(DataQualityFinding).where(DataQualityFinding.study_id == study_id)
    if status:
        stmt = stmt.where(DataQualityFinding.status == status)
    visible: list[DataQualityFinding] = []
    for row in session.scalars(stmt).all():
        if severity and row.rule.severity != severity:
            continue
        if row.subject_id is None:
            visible.append(row)
            continue
        subject = session.get(StudySubject, row.subject_id)
        if subject is not None and subject.site_id in site_ids:
            visible.append(row)
    return visible


_HANDLERS = {
    "numeric_range": _numeric_range,
    "required_effective": _required_effective,
    "missing_value": _missing_value,
    "max_finals": _max_finals,
    "duplicate_observation": _duplicate_observation,
    "visit_date_order": _visit_date_order,
    "questionnaire_complete": _questionnaire_complete,
    "questionnaire_incomplete": _questionnaire_incomplete,
    "revision_chain": _revision_chain,
    "provenance": _provenance,
    "cross_field": _cross_field,
}
