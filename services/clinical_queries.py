"""임상 질의 수명주기. 해결은 관찰 값을 바꾸지 않는다."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from models.clinical_support import (
    ClinicalObservation,
    ClinicalQuery,
    ClinicalQueryEvent,
    ClinicalQueryResponse,
    DataQualityFinding,
    QuestionnaireDefinition,
    StudySiteMember,
    StudySubject,
    StudyVisit,
)
from services.clinical_records import (
    ClinicalRecordError,
    _audit,
    _require_site_member,
    _require_study_member,
    correct_observation,
    list_sites_for_member,
)

QUERY_TRANSITIONS = {
    "open": {"answered"},
    "answered": {"resolved"},
    "resolved": {"reopened"},
    "reopened": {"answered"},
}


def create_query(
    session: Session,
    *,
    study_id: str,
    actor_user_id: str,
    category: str,
    severity: str,
    description: str,
    subject_id: str | None = None,
    visit_id: str | None = None,
    definition_id: str | None = None,
    observation_id: str | None = None,
    finding_id: str | None = None,
    assigned_user_id: str | None = None,
    assigned_role: str | None = None,
) -> ClinicalQuery:
    _require_text(category, "질의 분류가 필요합니다.")
    _require_text(severity, "질의 중증도가 필요합니다.")
    _require_text(description, "질의 설명이 필요합니다.")
    if not any((subject_id, visit_id, definition_id, observation_id, finding_id)):
        raise ClinicalRecordError("질의에는 대상 기록이 필요합니다.")
    site_id, subject_id, visit_id, observation_id = _bind_references(
        session,
        study_id=study_id,
        subject_id=subject_id,
        visit_id=visit_id,
        definition_id=definition_id,
        observation_id=observation_id,
        finding_id=finding_id,
    )
    _authorize(session, study_id, site_id, actor_user_id)
    if assigned_user_id or assigned_role:
        _check_assignment(session, site_id, study_id, assigned_user_id, assigned_role)
    query = ClinicalQuery(
        study_id=study_id,
        site_id=site_id,
        subject_id=subject_id,
        visit_id=visit_id,
        definition_id=definition_id,
        observation_id=observation_id,
        finding_id=finding_id,
        category=category.strip(),
        severity=severity.strip(),
        description=description.strip(),
        status="open",
        assigned_user_id=assigned_user_id,
        assigned_role=assigned_role,
        opened_by=actor_user_id,
        opened_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(query)
    session.flush()
    _event(session, query, None, "open", actor_user_id, "질의 생성")
    _audit(
        session,
        study_id=study_id,
        site_id=site_id,
        actor_user_id=actor_user_id,
        action="query_open",
        target_type="clinical_query",
        target_id=query.id,
        payload={"category": query.category, "severity": query.severity},
        request_id="phase007",
    )
    return query


def create_query_from_finding(
    session: Session,
    finding_id: str,
    *,
    actor_user_id: str,
    description: str | None = None,
) -> ClinicalQuery:
    finding = session.get(DataQualityFinding, finding_id)
    if finding is None:
        raise ClinicalRecordError("품질 소견이 없습니다.")
    observation_id = finding.target_id if finding.target_type == "observation" else None
    text = description or finding.message_code
    return create_query(
        session,
        study_id=finding.study_id,
        actor_user_id=actor_user_id,
        category="data_quality",
        severity=finding.rule.severity,
        description=text,
        subject_id=finding.subject_id,
        visit_id=finding.visit_id,
        observation_id=observation_id,
        finding_id=finding.id,
    )


def assign_query(
    session: Session,
    query_id: str,
    *,
    actor_user_id: str,
    reason: str,
    assigned_user_id: str | None = None,
    assigned_role: str | None = None,
) -> ClinicalQuery:
    query = _locked(session, query_id)
    _authorize(session, query.study_id, query.site_id, actor_user_id)
    _require_text(reason, "배정 사유가 필요합니다.")
    _check_assignment(session, query.site_id, query.study_id, assigned_user_id, assigned_role)
    query.assigned_user_id = assigned_user_id
    query.assigned_role = assigned_role
    query.updated_at = datetime.now(timezone.utc)
    _event(
        session, query, query.status, query.status, actor_user_id, reason.strip(),
        {"assigned_user_id": assigned_user_id, "assigned_role": assigned_role},
    )
    session.flush()
    return query


def respond_to_query(
    session: Session,
    query_id: str,
    *,
    actor_user_id: str,
    body: str,
) -> ClinicalQuery:
    query = _locked(session, query_id)
    _authorize(session, query.study_id, query.site_id, actor_user_id)
    _require_text(body, "질의 응답이 필요합니다.")
    _ensure_transition(query.status, "answered")
    response = ClinicalQueryResponse(
        query_id=query.id,
        author_user_id=actor_user_id,
        body=body.strip(),
        created_at=datetime.now(timezone.utc),
    )
    session.add(response)
    session.flush()
    before = query.status
    query.status = "answered"
    query.updated_at = datetime.now(timezone.utc)
    _event(session, query, before, "answered", actor_user_id, body.strip(), {"response_id": response.id})
    _audit(
        session, study_id=query.study_id, site_id=query.site_id, actor_user_id=actor_user_id,
        action="query_answer", target_type="clinical_query", target_id=query.id,
        payload={"response_id": response.id}, request_id="phase007",
    )
    session.flush()
    return query


def resolve_query(
    session: Session,
    query_id: str,
    *,
    actor_user_id: str,
    reason: str,
) -> ClinicalQuery:
    query = _locked(session, query_id)
    _authorize(session, query.study_id, query.site_id, actor_user_id)
    _require_text(reason, "해결 사유가 필요합니다.")
    before_row = _snapshot(session, query.observation_id)
    _ensure_transition(query.status, "resolved")
    previous = query.status
    query.status = "resolved"
    query.updated_at = datetime.now(timezone.utc)
    _event(session, query, previous, "resolved", actor_user_id, reason.strip())
    session.flush()
    if _snapshot(session, query.observation_id) != before_row:
        raise ClinicalRecordError("질의 해결이 관찰 값을 바꿨습니다.")
    _audit(
        session, study_id=query.study_id, site_id=query.site_id, actor_user_id=actor_user_id,
        action="query_resolve", target_type="clinical_query", target_id=query.id,
        payload={"reason": reason.strip()}, request_id="phase007",
    )
    return query


def reopen_query(
    session: Session,
    query_id: str,
    *,
    actor_user_id: str,
    reason: str,
) -> ClinicalQuery:
    query = _locked(session, query_id)
    _authorize(session, query.study_id, query.site_id, actor_user_id)
    _require_text(reason, "재오픈 사유가 필요합니다.")
    _ensure_transition(query.status, "reopened")
    previous = query.status
    query.status = "reopened"
    query.updated_at = datetime.now(timezone.utc)
    _event(session, query, previous, "reopened", actor_user_id, reason.strip())
    _audit(
        session, study_id=query.study_id, site_id=query.site_id, actor_user_id=actor_user_id,
        action="query_reopen", target_type="clinical_query", target_id=query.id,
        payload={"reason": reason.strip()}, request_id="phase007",
    )
    session.flush()
    return query


def correct_from_query(
    session: Session,
    query_id: str,
    *,
    actor_user_id: str,
    reason: str,
    value_number: float | None = None,
    value_text: str | None = None,
    unit: str | None = None,
) -> ClinicalObservation:
    query = _locked(session, query_id)
    _authorize(session, query.study_id, query.site_id, actor_user_id)
    if query.status == "resolved":
        raise ClinicalRecordError("해결된 질의에서는 정정을 시작하지 않습니다.")
    if query.observation_id is None:
        raise ClinicalRecordError("정정할 관찰이 질의에 없습니다.")
    prior = session.get(ClinicalObservation, query.observation_id)
    if prior is None:
        raise ClinicalRecordError("관찰이 없습니다.")
    prior_hash = prior.row_hash
    successor = correct_observation(
        session,
        prior.id,
        actor_user_id=actor_user_id,
        reason=reason,
        value_number=value_number,
        value_text=value_text,
        unit=unit,
    )
    session.refresh(prior)
    if prior.row_hash != prior_hash:
        raise ClinicalRecordError("이전 관찰이 변경되었습니다.")
    query.updated_at = datetime.now(timezone.utc)
    _event(
        session, query, query.status, query.status, actor_user_id, reason.strip(),
        {"successor_observation_id": successor.id, "prior_observation_id": prior.id},
    )
    session.flush()
    return successor


def list_queries(
    session: Session,
    *,
    study_id: str,
    actor_user_id: str,
    site_id: str | None = None,
    status: str | None = None,
    severity: str | None = None,
) -> list[ClinicalQuery]:
    _require_study_member(session, study_id, actor_user_id)
    site_ids = [site.id for site in list_sites_for_member(session, study_id, actor_user_id)]
    if site_id is not None and site_id not in site_ids:
        raise ClinicalRecordError("사이트 구성원이 아닙니다.")
    stmt = select(ClinicalQuery).where(ClinicalQuery.study_id == study_id)
    if site_id is not None:
        stmt = stmt.where(ClinicalQuery.site_id == site_id)
    else:
        stmt = stmt.where(or_(ClinicalQuery.site_id.is_(None), ClinicalQuery.site_id.in_(site_ids)))
    if status:
        stmt = stmt.where(ClinicalQuery.status == status)
    if severity:
        stmt = stmt.where(ClinicalQuery.severity == severity)
    return list(session.scalars(stmt.order_by(ClinicalQuery.opened_at)).all())


def get_query(session: Session, query_id: str, *, actor_user_id: str) -> ClinicalQuery:
    query = session.get(ClinicalQuery, query_id)
    if query is None:
        raise ClinicalRecordError("질의가 없습니다.")
    _authorize(session, query.study_id, query.site_id, actor_user_id)
    return query


def list_query_history(session: Session, query_id: str, *, actor_user_id: str) -> list[ClinicalQueryEvent]:
    query = get_query(session, query_id, actor_user_id=actor_user_id)
    stmt = (
        select(ClinicalQueryEvent)
        .where(ClinicalQueryEvent.query_id == query.id)
        .order_by(ClinicalQueryEvent.occurred_at, ClinicalQueryEvent.id)
    )
    return list(session.scalars(stmt).all())


def _authorize(session: Session, study_id: str, site_id: str | None, user_id: str) -> None:
    if site_id:
        _require_site_member(session, site_id, user_id)
        return
    _require_study_member(session, study_id, user_id)


def _bind_references(
    session: Session,
    *,
    study_id: str,
    subject_id: str | None,
    visit_id: str | None,
    definition_id: str | None,
    observation_id: str | None,
    finding_id: str | None,
) -> tuple[str | None, str | None, str | None, str | None]:
    site_id = None
    if finding_id is not None:
        finding = session.get(DataQualityFinding, finding_id)
        if finding is None or finding.study_id != study_id:
            raise ClinicalRecordError("품질 소견이 이 연구에 없습니다.")
    if definition_id is not None:
        definition = session.get(QuestionnaireDefinition, definition_id)
        if definition is None or definition.study_id != study_id:
            raise ClinicalRecordError("설문 정의가 이 연구에 없습니다.")
    if observation_id is not None:
        observation = session.get(ClinicalObservation, observation_id)
        if observation is None:
            raise ClinicalRecordError("관찰이 없습니다.")
        visit_id = observation.visit_id
    if visit_id is not None:
        visit = session.get(StudyVisit, visit_id)
        if visit is None:
            raise ClinicalRecordError("Visit 가 없습니다.")
        if subject_id and subject_id != visit.subject_id:
            raise ClinicalRecordError("Visit 가 대상자에 속하지 않습니다.")
        subject_id = visit.subject_id
    if subject_id is not None:
        subject = session.get(StudySubject, subject_id)
        if subject is None or subject.study_id != study_id:
            raise ClinicalRecordError("대상자가 이 연구에 없습니다.")
        site_id = subject.site_id
    return site_id, subject_id, visit_id, observation_id


def _check_assignment(
    session: Session,
    site_id: str | None,
    study_id: str,
    assigned_user_id: str | None,
    assigned_role: str | None,
) -> None:
    if bool(assigned_user_id) == bool(assigned_role):
        raise ClinicalRecordError("배정 대상은 사용자 또는 역할 중 하나입니다.")
    if assigned_user_id:
        if site_id:
            _require_site_member(session, site_id, assigned_user_id)
        else:
            _require_study_member(session, study_id, assigned_user_id)
        return
    stmt = select(StudySiteMember.id).where(StudySiteMember.role == assigned_role)
    if site_id:
        stmt = stmt.where(StudySiteMember.site_id == site_id)
    else:
        from models.clinical_support import StudySite
        stmt = stmt.join(StudySite, StudySite.id == StudySiteMember.site_id).where(
            StudySite.study_id == study_id
        )
    if session.scalar(stmt) is None:
        raise ClinicalRecordError("배정할 역할의 구성원이 없습니다.")


def _locked(session: Session, query_id: str) -> ClinicalQuery:
    stmt = select(ClinicalQuery).where(ClinicalQuery.id == query_id)
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update()
    query = session.scalar(stmt)
    if query is None:
        raise ClinicalRecordError("질의가 없습니다.")
    return query


def _ensure_transition(current: str, target: str) -> None:
    if target not in QUERY_TRANSITIONS.get(current, set()):
        raise ClinicalRecordError("허용되지 않는 질의 전이입니다.")


def _event(
    session: Session,
    query: ClinicalQuery,
    from_status: str | None,
    to_status: str,
    actor_user_id: str,
    reason: str,
    detail: dict | None = None,
) -> None:
    session.add(ClinicalQueryEvent(
        query_id=query.id,
        from_status=from_status,
        to_status=to_status,
        actor_user_id=actor_user_id,
        reason=reason,
        detail_json=None if detail is None else json.dumps(detail, sort_keys=True),
        occurred_at=datetime.now(timezone.utc),
    ))
    session.flush()


def _snapshot(session: Session, observation_id: str | None):
    if observation_id is None:
        return None
    row = session.get(ClinicalObservation, observation_id)
    if row is None:
        return None
    return (row.id, row.value_number, row.row_hash, row.revision)


def _require_text(value: str, message: str) -> None:
    if not value or not str(value).strip():
        raise ClinicalRecordError(message)
