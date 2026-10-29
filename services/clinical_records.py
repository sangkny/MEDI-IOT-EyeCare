"""임상 레코드 기초 서비스.

세션은 호출자가 연다. 이 모듈은 database.py 엔진을 사용하지 않고,
DeeVo 나 운영 데이터베이스에 연결하지 않는다.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from models.clinical import ClinicalStudy, StudyStatusEnum
from models.clinical_support import (
    AuditEventChain,
    ClinicalAuditEvent,
    ClinicalObservation,
    DataLockState,
    DataQualityFinding,
    DataQualityRule,
    QuestionnaireDefinition,
    QuestionnaireResponse,
    QuestionnaireResponseItem,
    QuestionnaireVersion,
    VisitFormAssignment,
    StudySite,
    StudySiteMember,
    StudySubject,
    StudyVisit,
    VisitWindow,
)

_IDENTIFYING = frozenset({
    "name",
    "patient_name",
    "mrn",
    "chart_no",
    "medical_record_number",
    "resident_number",
    "treatment_arm",
    "allocation",
    "unblinded",
})


class ClinicalRecordError(ValueError):
    """호출 계약 위반. 원본 행은 바꾸지 않는다."""


def _canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)


def _hash(payload: dict) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def verify_audit_integrity(event: ClinicalAuditEvent) -> dict:
    """저장된 직렬화와 해시를 비교한다. 해시만으로 규제 준수를 의미하지 않는다."""
    if not event.payload_json:
        return {
            "status": "LEGACY_HASH_ONLY",
            "matches": None,
            "regulatory_compliance": False,
        }
    digest = hashlib.sha256(event.payload_json.encode("utf-8")).hexdigest()
    return {
        "status": "MATCH" if digest == event.payload_hash else "MISMATCH",
        "matches": digest == event.payload_hash,
        "regulatory_compliance": False,
    }


_AUDIT_GENESIS = "0" * 64


def _append_audit_chain(
    session: Session,
    event: ClinicalAuditEvent,
    *,
    actor_role: str | None,
    protocol_version: str | None,
    schema_version_id: str | None,
    correlation_id: str,
) -> None:
    previous = session.scalar(
        select(AuditEventChain)
        .where(AuditEventChain.study_id == event.study_id)
        .order_by(AuditEventChain.chain_seq.desc())
        .limit(1)
    )
    previous_hash = previous.event_hash if previous is not None else _AUDIT_GENESIS
    chain_seq = 1 if previous is None else previous.chain_seq + 1
    material = _canonical({
        "event_id": event.id,
        "previous_hash": previous_hash,
        "action": event.action,
        "target_id": event.target_id,
        "payload_hash": event.payload_hash,
    })
    session.add(AuditEventChain(
        event_id=event.id,
        chain_seq=chain_seq,
        study_id=event.study_id,
        actor_role=actor_role,
        protocol_version=protocol_version,
        schema_version_id=schema_version_id,
        correlation_id=correlation_id,
        previous_hash=previous_hash,
        event_hash=hashlib.sha256(material.encode("utf-8")).hexdigest(),
    ))
    session.flush()


def _audit(
    session: Session,
    *,
    study_id: str,
    actor_user_id: str,
    action: str,
    target_type: str,
    target_id: str,
    payload: dict,
    site_id: str | None = None,
    request_id: str = "phase004",
    previous_state: str | None = None,
    new_state: str | None = None,
    reason: str | None = None,
    target_revision: int | None = None,
    actor_role: str | None = None,
    protocol_version: str | None = None,
    schema_version_id: str | None = None,
    correlation_id: str | None = None,
    link_chain: bool = False,
) -> ClinicalAuditEvent:
    raw = _canonical(payload)
    event = ClinicalAuditEvent(
        study_id=study_id,
        site_id=site_id,
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        occurred_at=datetime.now(timezone.utc),
        request_id=request_id,
        payload_hash=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        payload_json=raw,
        previous_state=previous_state,
        new_state=new_state,
        reason=reason,
        target_revision=target_revision,
    )
    session.add(event)
    if link_chain or session.info.get("link_audit_chain"):
        session.flush()
        _append_audit_chain(
            session,
            event,
            actor_role=actor_role,
            protocol_version=protocol_version,
            schema_version_id=schema_version_id,
            correlation_id=correlation_id or str(uuid.uuid4()),
        )
    return event


def _assert_not_locked(
    session: Session,
    *,
    study_id: str,
    subject_id: str | None = None,
    visit_id: str | None = None,
    record_type: str | None = None,
    record_id: str | None = None,
) -> None:
    connection = session.connection()
    if not inspect(connection).has_table(DataLockState.__tablename__):
        return
    keys = [("study", study_id)]
    if subject_id:
        keys.append(("subject", subject_id))
    if visit_id:
        keys.append(("visit", visit_id))
    if record_type and record_id:
        keys.append((record_type, record_id))
    rows = session.scalars(
        select(DataLockState).where(
            DataLockState.study_id == study_id,
            DataLockState.state.in_(("LOCKED", "UNLOCK_REQUESTED")),
        )
    ).all()
    blocked = {(row.target_type, row.target_id) for row in rows}
    if any(key in blocked for key in keys):
        raise ClinicalRecordError("잠긴 임상 데이터는 수정할 수 없습니다.")


def create_study(
    session: Session,
    *,
    code: str,
    name: str,
    study_kind: str = "dataset",
    protocol_version: str | None = None,
    description: str | None = None,
    actor_user_id: str = "system",
) -> ClinicalStudy:
    if study_kind not in {"dataset", "prospective"}:
        raise ClinicalRecordError("study_kind 는 dataset 또는 prospective 입니다.")
    study = ClinicalStudy(
        code=code,
        name=name,
        study_kind=study_kind,
        protocol_version=protocol_version,
        description=description,
        status=StudyStatusEnum.DRAFT.value,
    )
    session.add(study)
    session.flush()
    _audit(
        session,
        study_id=study.id,
        actor_user_id=actor_user_id,
        action="create",
        target_type="study",
        target_id=study.id,
        payload={"code": code, "study_kind": study_kind},
    )
    return study


def get_study(session: Session, study_id: str) -> ClinicalStudy | None:
    return session.get(ClinicalStudy, study_id)


def add_site(
    session: Session,
    *,
    study_id: str,
    site_code: str,
    name: str,
    actor_user_id: str,
) -> StudySite:
    if get_study(session, study_id) is None:
        raise ClinicalRecordError("연구가 없습니다.")
    site = StudySite(study_id=study_id, site_code=site_code, name=name)
    session.add(site)
    session.flush()
    _audit(
        session,
        study_id=study_id,
        site_id=site.id,
        actor_user_id=actor_user_id,
        action="create",
        target_type="site",
        target_id=site.id,
        payload={"site_code": site_code},
    )
    return site


def add_site_member(
    session: Session,
    *,
    site_id: str,
    user_id: str,
    role: str,
    actor_user_id: str,
) -> StudySiteMember:
    site = session.get(StudySite, site_id)
    if site is None:
        raise ClinicalRecordError("사이트가 없습니다.")
    member = StudySiteMember(site_id=site_id, user_id=user_id, role=role)
    session.add(member)
    session.flush()
    _audit(
        session,
        study_id=site.study_id,
        site_id=site_id,
        actor_user_id=actor_user_id,
        action="create",
        target_type="site_member",
        target_id=member.id,
        payload={"role": role},
    )
    return member


def enroll_subject(
    session: Session,
    *,
    study_id: str,
    site_id: str,
    subject_code: str,
    actor_user_id: str,
    patient_id: str | None = None,
    enrolled_on: date | None = None,
) -> StudySubject:
    if not subject_code.strip():
        raise ClinicalRecordError("subject_code 가 비어 있습니다.")
    _require_site_member(session, site_id, actor_user_id)
    site = session.get(StudySite, site_id)
    if site is None or site.study_id != study_id:
        raise ClinicalRecordError("사이트가 이 연구에 속하지 않습니다.")
    subject = StudySubject(
        study_id=study_id,
        site_id=site_id,
        subject_code=subject_code,
        patient_id=patient_id,
        enrolled_on=enrolled_on,
    )
    session.add(subject)
    session.flush()
    _audit(
        session,
        study_id=study_id,
        site_id=site_id,
        actor_user_id=actor_user_id,
        action="create",
        target_type="subject",
        target_id=subject.id,
        payload={"subject_code": subject_code},
    )
    return subject


def list_subjects(session: Session, study_id: str) -> list[StudySubject]:
    stmt = select(StudySubject).where(StudySubject.study_id == study_id)
    return list(session.scalars(stmt).all())


def open_visit(
    session: Session,
    *,
    subject_id: str,
    visit_code: str,
    occurred_on: date,
    actor_user_id: str,
    repeat_no: int = 1,
    window_id: str | None = None,
) -> StudyVisit:
    subject = session.get(StudySubject, subject_id)
    if subject is None:
        raise ClinicalRecordError("대상자가 없습니다.")
    _require_site_member(session, subject.site_id, actor_user_id)
    _assert_not_locked(session, study_id=subject.study_id, subject_id=subject.id)
    if window_id is not None:
        window = session.get(VisitWindow, window_id)
        if window is None or window.study_id != subject.study_id:
            raise ClinicalRecordError("Visit 창이 이 연구에 속하지 않습니다.")
        if window.visit_code != visit_code:
            raise ClinicalRecordError("Visit 코드가 창과 다릅니다.")
    visit = StudyVisit(
        subject_id=subject_id,
        visit_code=visit_code,
        occurred_on=occurred_on,
        repeat_no=repeat_no,
        window_id=window_id,
    )
    session.add(visit)
    session.flush()
    _audit(
        session,
        study_id=subject.study_id,
        site_id=subject.site_id,
        actor_user_id=actor_user_id,
        action="create",
        target_type="visit",
        target_id=visit.id,
        payload={"visit_code": visit_code, "repeat_no": repeat_no},
    )
    return visit


def define_questionnaire(
    session: Session,
    *,
    study_id: str,
    code: str,
    title: str,
    actor_user_id: str,
) -> QuestionnaireDefinition:
    _require_study_member(session, study_id, actor_user_id)
    row = QuestionnaireDefinition(study_id=study_id, code=code, title=title)
    session.add(row)
    session.flush()
    return row


def publish_questionnaire_version(
    session: Session,
    *,
    definition_id: str,
    version_number: int,
    items_json: str,
    actor_user_id: str,
) -> QuestionnaireVersion:
    definition = session.get(QuestionnaireDefinition, definition_id)
    if definition is None:
        raise ClinicalRecordError("설문 정의가 없습니다.")
    _require_study_member(session, definition.study_id, actor_user_id)
    version = QuestionnaireVersion(
        definition_id=definition_id,
        version_number=version_number,
        items_json=items_json,
        content_hash=_hash({"items_json": items_json, "version_number": version_number}),
    )
    session.add(version)
    session.flush()
    _audit(
        session,
        study_id=definition.study_id,
        actor_user_id=actor_user_id,
        action="create",
        target_type="questionnaire_version",
        target_id=version.id,
        payload={"version_number": version_number, "content_hash": version.content_hash},
    )
    return version


def start_response(
    session: Session,
    *,
    version_id: str,
    visit_id: str,
    recorded_by: str,
    actor_user_id: str | None = None,
) -> QuestionnaireResponse:
    version = session.get(QuestionnaireVersion, version_id)
    visit = session.get(StudyVisit, visit_id)
    if version is None or visit is None:
        raise ClinicalRecordError("설문 버전 또는 Visit 가 없습니다.")
    if version.definition.study_id != visit.subject.study_id:
        raise ClinicalRecordError("설문과 Visit 의 연구가 다릅니다.")
    _require_site_member(session, visit.subject.site_id, actor_user_id or recorded_by)
    _assert_not_locked(
        session,
        study_id=visit.subject.study_id,
        subject_id=visit.subject_id,
        visit_id=visit.id,
    )
    response = QuestionnaireResponse(
        version_id=version_id,
        visit_id=visit_id,
        recorded_by=recorded_by,
        status="draft",
    )
    session.add(response)
    session.flush()
    return response


def _observation_hash(row: ClinicalObservation) -> str:
    return _hash({
        "visit_id": row.visit_id,
        "code": row.code,
        "laterality": row.laterality,
        "method": row.method,
        "repeat_index": row.repeat_index,
        "revision": row.revision,
        "value_number": None if row.value_number is None else str(row.value_number),
        "value_text": row.value_text,
        "unit": row.unit,
        "source": row.source,
        "record_status": row.record_status,
        "correction_reason": row.correction_reason,
        "supersedes_observation_id": row.supersedes_observation_id,
    })


def record_observation(
    session: Session,
    *,
    visit_id: str,
    code: str,
    recorded_by: str,
    laterality: str = "NA",
    method: str = "NA",
    repeat_index: int = 1,
    value_number: float | None = None,
    value_text: str | None = None,
    unit: str | None = None,
    source: str = "manual",
    actor_user_id: str | None = None,
) -> ClinicalObservation:
    """즉시 확정 경로도 초안 작성과 확정 검사를 그대로 통과한다."""
    actor = actor_user_id or recorded_by
    draft = create_draft_observation(
        session,
        visit_id=visit_id,
        code=code,
        recorded_by=recorded_by,
        actor_user_id=actor,
        laterality=laterality,
        method=method,
        repeat_index=repeat_index,
        value_number=value_number,
        value_text=value_text,
        unit=unit,
    )
    if source != "manual":
        draft.source = source
        draft.row_hash = _observation_hash(draft)
        session.flush()
    return finalize_observation(session, draft.id, actor_user_id=actor)


def supersede_observation(
    session: Session,
    observation_id: str,
    *,
    recorded_by: str,
    reason: str,
    value_number: float | None = None,
    value_text: str | None = None,
    unit: str | None = None,
    actor_user_id: str | None = None,
) -> ClinicalObservation:
    """확정 관찰은 수정하지 않는다. 사유가 있는 현재 유효 개정만 새 revision으로 남긴다."""
    return correct_observation(
        session,
        observation_id,
        actor_user_id=actor_user_id or recorded_by,
        reason=reason,
        value_number=value_number,
        value_text=value_text,
        unit=unit,
    )


def record_quality_finding(
    session: Session,
    *,
    rule_id: str,
    study_id: str,
    target_type: str,
    target_id: str,
    fingerprint: str,
    message_code: str,
    actor_user_id: str,
    subject_id: str | None = None,
    visit_id: str | None = None,
    source_revision: int | None = None,
    evaluation_scope: str = "study",
    evaluation_scope_id: str | None = None,
) -> DataQualityFinding:
    rule = session.get(DataQualityRule, rule_id)
    if rule is None or rule.study_id != study_id:
        raise ClinicalRecordError("품질 규칙이 이 연구에 없습니다.")
    finding = DataQualityFinding(
        rule_id=rule.id,
        rule_version=rule.version_number,
        study_id=study_id,
        subject_id=subject_id,
        visit_id=visit_id,
        target_type=target_type,
        target_id=target_id,
        fingerprint=fingerprint,
        message_code=message_code,
        status="open",
        source_revision=source_revision,
        evaluation_scope=evaluation_scope,
        evaluation_scope_id=evaluation_scope_id,
        evaluated_at=datetime.now(timezone.utc),
    )
    session.add(finding)
    session.flush()
    _audit(
        session,
        study_id=study_id,
        actor_user_id=actor_user_id,
        action="quality_open",
        target_type="quality_finding",
        target_id=finding.id,
        payload={"message_code": message_code, "fingerprint": fingerprint},
    )
    return finding


def add_quality_rule(
    session: Session,
    *,
    study_id: str,
    code: str,
    version_number: int,
    severity: str,
    logic_json: str,
) -> DataQualityRule:
    rule = DataQualityRule(
        study_id=study_id,
        code=code,
        version_number=version_number,
        severity=severity,
        logic_json=logic_json,
        content_hash=_hash({"logic_json": logic_json, "version_number": version_number}),
    )
    session.add(rule)
    session.flush()
    return rule


def subject_columns() -> set[str]:
    return {column.name for column in StudySubject.__table__.columns}


def _require_site_member(session: Session, site_id: str, user_id: str) -> StudySiteMember:
    member = session.scalar(
        select(StudySiteMember).where(
            StudySiteMember.site_id == site_id,
            StudySiteMember.user_id == user_id,
        )
    )
    if member is None:
        raise ClinicalRecordError("사이트 구성원이 아닙니다.")
    return member


def _require_study_member(session: Session, study_id: str, user_id: str) -> None:
    member_id = session.scalar(
        select(StudySiteMember.id)
        .join(StudySite, StudySite.id == StudySiteMember.site_id)
        .where(StudySite.study_id == study_id, StudySiteMember.user_id == user_id)
    )
    if member_id is None:
        raise ClinicalRecordError("연구 구성원이 아닙니다.")


def _series(
    session: Session,
    *,
    visit_id: str,
    code: str,
    laterality: str,
    method: str,
    repeat_index: int,
    lock: bool,
) -> list[ClinicalObservation]:
    stmt = (
        select(ClinicalObservation)
        .where(
            ClinicalObservation.visit_id == visit_id,
            ClinicalObservation.code == code,
            ClinicalObservation.laterality == laterality,
            ClinicalObservation.method == method,
            ClinicalObservation.repeat_index == repeat_index,
        )
        .order_by(ClinicalObservation.revision)
    )
    bind = session.get_bind()
    if lock and bind is not None and bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update()
    return list(session.scalars(stmt).all())


def _require_value(row: ClinicalObservation) -> None:
    if row.value_number is None and not (row.value_text and row.value_text.strip()):
        raise ClinicalRecordError("확정하려면 측정값이 필요합니다.")


def create_draft_observation(
    session: Session,
    *,
    visit_id: str,
    code: str,
    recorded_by: str,
    actor_user_id: str,
    laterality: str = "NA",
    method: str = "NA",
    repeat_index: int = 1,
    value_number: float | None = None,
    value_text: str | None = None,
    unit: str | None = None,
    source: str = "manual",
) -> ClinicalObservation:
    visit = session.get(StudyVisit, visit_id)
    if visit is None:
        raise ClinicalRecordError("Visit 가 없습니다.")
    _require_site_member(session, visit.subject.site_id, actor_user_id)
    _assert_not_locked(
        session,
        study_id=visit.subject.study_id,
        subject_id=visit.subject_id,
        visit_id=visit.id,
    )
    existing = _series(
        session,
        visit_id=visit_id,
        code=code,
        laterality=laterality,
        method=method,
        repeat_index=repeat_index,
        lock=True,
    )
    if existing:
        raise ClinicalRecordError("같은 측정 키가 이미 있습니다. 정정 경로를 사용합니다.")
    row = ClinicalObservation(
        visit_id=visit_id,
        code=code,
        laterality=laterality,
        method=method,
        repeat_index=repeat_index,
        revision=1,
        value_number=value_number,
        value_text=value_text,
        unit=unit,
        source=source,
        record_status="draft",
        recorded_by=recorded_by,
        recorded_at=datetime.now(timezone.utc),
        row_hash="pending",
    )
    row.row_hash = _observation_hash(row)
    session.add(row)
    session.flush()
    _audit(
        session,
        study_id=visit.subject.study_id,
        site_id=visit.subject.site_id,
        actor_user_id=actor_user_id,
        action="create",
        target_type="observation",
        target_id=row.id,
        payload={"code": code, "record_status": "draft", "row_hash": row.row_hash},
    )
    return row


_UNSET = object()


def update_draft_observation(
    session: Session,
    observation_id: str,
    *,
    actor_user_id: str,
    value_number: float | None | object = _UNSET,
    value_text: str | None | object = _UNSET,
    unit: str | None | object = _UNSET,
) -> ClinicalObservation:
    row = session.get(ClinicalObservation, observation_id)
    if row is None:
        raise ClinicalRecordError("관찰이 없습니다.")
    if row.record_status != "draft":
        raise ClinicalRecordError("확정된 관찰은 수정할 수 없습니다.")
    visit = session.get(StudyVisit, row.visit_id)
    if visit is None:
        raise ClinicalRecordError("Visit 가 없습니다.")
    _require_site_member(session, visit.subject.site_id, actor_user_id)
    _assert_not_locked(
        session,
        study_id=visit.subject.study_id,
        subject_id=visit.subject_id,
        visit_id=visit.id,
        record_type="observation",
        record_id=row.id,
    )
    if value_number is not _UNSET:
        row.value_number = value_number
    if value_text is not _UNSET:
        row.value_text = value_text
    if unit is not _UNSET:
        row.unit = unit
    row.row_hash = _observation_hash(row)
    session.flush()
    _audit(
        session,
        study_id=visit.subject.study_id,
        site_id=visit.subject.site_id,
        actor_user_id=actor_user_id,
        action="create",
        target_type="observation_draft",
        target_id=row.id,
        payload={"row_hash": row.row_hash},
    )
    return row


def finalize_observation(
    session: Session,
    observation_id: str,
    *,
    actor_user_id: str,
) -> ClinicalObservation:
    row = session.get(ClinicalObservation, observation_id)
    if row is None:
        raise ClinicalRecordError("관찰이 없습니다.")
    if row.record_status != "draft":
        raise ClinicalRecordError("초안만 확정할 수 있습니다.")
    visit = session.get(StudyVisit, row.visit_id)
    if visit is None:
        raise ClinicalRecordError("Visit 가 없습니다.")
    _require_site_member(session, visit.subject.site_id, actor_user_id)
    _assert_not_locked(
        session,
        study_id=visit.subject.study_id,
        subject_id=visit.subject_id,
        visit_id=visit.id,
        record_type="observation",
        record_id=row.id,
    )
    _require_value(row)
    row.record_status = "final"
    row.finalized_by = actor_user_id
    row.finalized_at = datetime.now(timezone.utc)
    row.row_hash = _observation_hash(row)
    session.flush()
    _audit(
        session,
        study_id=visit.subject.study_id,
        site_id=visit.subject.site_id,
        actor_user_id=actor_user_id,
        action="complete",
        target_type="observation",
        target_id=row.id,
        payload={"record_status": "final", "row_hash": row.row_hash},
    )
    return row


def get_effective_observation(
    session: Session,
    *,
    visit_id: str,
    code: str,
    laterality: str = "NA",
    method: str = "NA",
    repeat_index: int = 1,
) -> ClinicalObservation | None:
    stmt = (
        select(ClinicalObservation)
        .where(
            ClinicalObservation.visit_id == visit_id,
            ClinicalObservation.code == code,
            ClinicalObservation.laterality == laterality,
            ClinicalObservation.method == method,
            ClinicalObservation.repeat_index == repeat_index,
            ClinicalObservation.record_status == "final",
        )
        .order_by(ClinicalObservation.revision.desc())
        .limit(1)
    )
    return session.scalar(stmt)


def list_observation_history(
    session: Session,
    *,
    visit_id: str,
    code: str,
    laterality: str = "NA",
    method: str = "NA",
    repeat_index: int = 1,
) -> list[ClinicalObservation]:
    return _series(
        session,
        visit_id=visit_id,
        code=code,
        laterality=laterality,
        method=method,
        repeat_index=repeat_index,
        lock=False,
    )


def correct_observation(
    session: Session,
    observation_id: str,
    *,
    actor_user_id: str,
    reason: str,
    value_number: float | None = None,
    value_text: str | None = None,
    unit: str | None = None,
) -> ClinicalObservation:
    if not reason or not reason.strip():
        raise ClinicalRecordError("정정 사유가 필요합니다.")
    prior = session.get(ClinicalObservation, observation_id)
    if prior is None:
        raise ClinicalRecordError("관찰이 없습니다.")
    if prior.record_status != "final":
        raise ClinicalRecordError("확정된 관찰만 정정할 수 있습니다.")
    visit = session.get(StudyVisit, prior.visit_id)
    if visit is None:
        raise ClinicalRecordError("Visit 가 없습니다.")
    _require_site_member(session, visit.subject.site_id, actor_user_id)
    _assert_not_locked(
        session,
        study_id=visit.subject.study_id,
        subject_id=visit.subject_id,
        visit_id=visit.id,
        record_type="observation",
        record_id=prior.id,
    )
    series = _series(
        session,
        visit_id=prior.visit_id,
        code=prior.code,
        laterality=prior.laterality,
        method=prior.method,
        repeat_index=prior.repeat_index,
        lock=True,
    )
    finals = [row for row in series if row.record_status == "final"]
    effective = max(finals, key=lambda row: row.revision)
    if effective.id != prior.id:
        raise ClinicalRecordError("현재 유효 개정만 정정할 수 있습니다.")
    prior_value = prior.value_number
    prior_hash = prior.row_hash
    next_revision = max(row.revision for row in series) + 1
    successor = ClinicalObservation(
        visit_id=prior.visit_id,
        code=prior.code,
        laterality=prior.laterality,
        method=prior.method,
        repeat_index=prior.repeat_index,
        revision=next_revision,
        value_number=value_number,
        value_text=value_text if value_text is not None else prior.value_text,
        unit=unit if unit is not None else prior.unit,
        source=prior.source,
        supersedes_observation_id=prior.id,
        record_status="final",
        correction_reason=reason.strip(),
        finalized_by=actor_user_id,
        finalized_at=datetime.now(timezone.utc),
        recorded_by=actor_user_id,
        recorded_at=datetime.now(timezone.utc),
        row_hash="pending",
    )
    successor.row_hash = _observation_hash(successor)
    session.add(successor)
    session.flush()
    session.refresh(prior)
    if prior.value_number != prior_value or prior.row_hash != prior_hash:
        raise ClinicalRecordError("이전 관찰이 변경되었습니다.")
    _audit(
        session,
        study_id=visit.subject.study_id,
        site_id=visit.subject.site_id,
        actor_user_id=actor_user_id,
        action="amend",
        target_type="observation",
        target_id=successor.id,
        payload={
            "supersedes_observation_id": prior.id,
            "revision": successor.revision,
            "reason": reason.strip(),
            "row_hash": successor.row_hash,
        },
    )
    return successor


def list_authorized_studies(session: Session, user_id: str) -> list[ClinicalStudy]:
    stmt = (
        select(ClinicalStudy)
        .join(StudySite, StudySite.study_id == ClinicalStudy.id)
        .join(StudySiteMember, StudySiteMember.site_id == StudySite.id)
        .where(StudySiteMember.user_id == user_id)
        .distinct()
        .order_by(ClinicalStudy.code)
    )
    return list(session.scalars(stmt).all())


def list_sites_for_member(session: Session, study_id: str, user_id: str) -> list[StudySite]:
    _require_study_member(session, study_id, user_id)
    stmt = (
        select(StudySite)
        .join(StudySiteMember, StudySiteMember.site_id == StudySite.id)
        .where(StudySite.study_id == study_id, StudySiteMember.user_id == user_id)
        .order_by(StudySite.site_code)
    )
    return list(session.scalars(stmt).all())


def list_site_members(session: Session, study_id: str, user_id: str) -> list[StudySiteMember]:
    _require_study_member(session, study_id, user_id)
    site_ids = select(StudySite.id).where(StudySite.study_id == study_id)
    visible = select(StudySiteMember.site_id).where(StudySiteMember.user_id == user_id)
    stmt = select(StudySiteMember).where(
        StudySiteMember.site_id.in_(site_ids),
        StudySiteMember.site_id.in_(visible),
    )
    return list(session.scalars(stmt).all())


def get_authorized_subject(session: Session, subject_id: str, user_id: str) -> StudySubject:
    subject = session.get(StudySubject, subject_id)
    if subject is None:
        raise ClinicalRecordError("대상자가 없습니다.")
    _require_site_member(session, subject.site_id, user_id)
    return subject


def list_visible_subjects(
    session: Session,
    study_id: str,
    user_id: str,
    site_id: str | None = None,
) -> list[StudySubject]:
    _require_study_member(session, study_id, user_id)
    visible = select(StudySiteMember.site_id).where(StudySiteMember.user_id == user_id)
    stmt = select(StudySubject).where(
        StudySubject.study_id == study_id,
        StudySubject.site_id.in_(visible),
    )
    if site_id is not None:
        _require_site_member(session, site_id, user_id)
        stmt = stmt.where(StudySubject.site_id == site_id)
    return list(session.scalars(stmt).all())


def list_subject_visits(session: Session, subject_id: str, user_id: str) -> list[StudyVisit]:
    subject = get_authorized_subject(session, subject_id, user_id)
    stmt = select(StudyVisit).where(StudyVisit.subject_id == subject.id).order_by(StudyVisit.occurred_on)
    return list(session.scalars(stmt).all())


def assign_visit_form(
    session: Session,
    *,
    study_id: str,
    visit_code: str,
    definition_id: str,
    actor_user_id: str,
) -> VisitFormAssignment:
    _require_study_member(session, study_id, actor_user_id)
    definition = session.get(QuestionnaireDefinition, definition_id)
    if definition is None or definition.study_id != study_id:
        raise ClinicalRecordError("설문 정의가 이 연구에 없습니다.")
    row = VisitFormAssignment(
        study_id=study_id, visit_code=visit_code, definition_id=definition_id,
    )
    session.add(row)
    session.flush()
    return row


def _item_spec(version: QuestionnaireVersion) -> list[dict]:
    try:
        parsed = json.loads(version.items_json)
    except json.JSONDecodeError as exc:
        raise ClinicalRecordError("설문 문항 JSON 이 올바르지 않습니다.") from exc
    if isinstance(parsed, dict):
        parsed = parsed.get("items")
    if not isinstance(parsed, list):
        raise ClinicalRecordError("설문 문항은 목록이어야 합니다.")
    return parsed


def save_response_item(
    session: Session,
    response_id: str,
    *,
    actor_user_id: str,
    item_code: str,
    value_json: str,
) -> QuestionnaireResponseItem:
    response = session.get(QuestionnaireResponse, response_id)
    if response is None:
        raise ClinicalRecordError("설문 응답이 없습니다.")
    if response.status != "draft":
        raise ClinicalRecordError("확정된 설문 응답은 수정할 수 없습니다.")
    visit = session.get(StudyVisit, response.visit_id)
    if visit is None:
        raise ClinicalRecordError("Visit 가 없습니다.")
    _require_site_member(session, visit.subject.site_id, actor_user_id)
    _assert_not_locked(
        session,
        study_id=visit.subject.study_id,
        subject_id=visit.subject_id,
        visit_id=visit.id,
        record_type="questionnaire_response",
        record_id=response.id,
    )
    known = {item.get("code") for item in _item_spec(response.version)}
    if item_code not in known:
        raise ClinicalRecordError("버전에 없는 문항입니다.")
    existing = session.scalar(
        select(QuestionnaireResponseItem).where(
            QuestionnaireResponseItem.response_id == response_id,
            QuestionnaireResponseItem.item_code == item_code,
        )
    )
    if existing is None:
        existing = QuestionnaireResponseItem(
            response_id=response_id, item_code=item_code, value_json=value_json,
        )
        session.add(existing)
    else:
        existing.value_json = value_json
    session.flush()
    return existing


def response_errors(session: Session, response: QuestionnaireResponse) -> list[str]:
    answers = {
        item.item_code: item.value_json
        for item in session.scalars(
            select(QuestionnaireResponseItem).where(
                QuestionnaireResponseItem.response_id == response.id
            )
        ).all()
    }
    errors: list[str] = []
    for spec in _item_spec(response.version):
        code = str(spec.get("code", ""))
        raw = answers.get(code)
        if spec.get("required") and (raw is None or raw == ""):
            errors.append(f"required:{code}")
            continue
        if raw is None or spec.get("type") != "number":
            continue
        try:
            parsed_value = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            errors.append(f"type:{code}")
            continue
        if spec.get("allows_not_applicable") and str(parsed_value).upper() in {
            "NA", "N/A", "해당없음",
        }:
            continue
        try:
            number = float(parsed_value)
        except (TypeError, ValueError):
            errors.append(f"type:{code}")
            continue
        if "min" in spec and number < float(spec["min"]):
            errors.append(f"min:{code}")
        if "max" in spec and number > float(spec["max"]):
            errors.append(f"max:{code}")
    return errors


def finalize_response(session: Session, response_id: str, *, actor_user_id: str) -> QuestionnaireResponse:
    response = session.get(QuestionnaireResponse, response_id)
    if response is None:
        raise ClinicalRecordError("설문 응답이 없습니다.")
    if response.status != "draft":
        raise ClinicalRecordError("초안 응답만 확정할 수 있습니다.")
    visit = session.get(StudyVisit, response.visit_id)
    if visit is None:
        raise ClinicalRecordError("Visit 가 없습니다.")
    _require_site_member(session, visit.subject.site_id, actor_user_id)
    _assert_not_locked(
        session,
        study_id=visit.subject.study_id,
        subject_id=visit.subject_id,
        visit_id=visit.id,
        record_type="questionnaire_response",
        record_id=response.id,
    )
    errors = response_errors(session, response)
    if errors:
        raise ClinicalRecordError("설문 검증 실패: " + ",".join(errors))
    response.status = "final"
    response.finalized_by = actor_user_id
    response.finalized_at = datetime.now(timezone.utc)
    response.content_hash = _hash({"response_id": response.id, "status": "final"})
    session.flush()
    return response


def correct_response(
    session: Session,
    response_id: str,
    *,
    actor_user_id: str,
    reason: str,
) -> QuestionnaireResponse:
    if not reason or not reason.strip():
        raise ClinicalRecordError("정정 사유가 필요합니다.")
    prior = session.get(QuestionnaireResponse, response_id)
    if prior is None:
        raise ClinicalRecordError("설문 응답이 없습니다.")
    if prior.status != "final":
        raise ClinicalRecordError("확정된 설문 응답만 정정할 수 있습니다.")
    visit = session.get(StudyVisit, prior.visit_id)
    if visit is None:
        raise ClinicalRecordError("Visit 가 없습니다.")
    _require_site_member(session, visit.subject.site_id, actor_user_id)
    _assert_not_locked(
        session,
        study_id=visit.subject.study_id,
        subject_id=visit.subject_id,
        visit_id=visit.id,
        record_type="questionnaire_response",
        record_id=prior.id,
    )
    successor = QuestionnaireResponse(
        version_id=prior.version_id,
        visit_id=prior.visit_id,
        status="draft",
        recorded_by=actor_user_id,
        supersedes_response_id=prior.id,
        correction_reason=reason.strip(),
    )
    session.add(successor)
    session.flush()
    for item in prior.items:
        session.add(QuestionnaireResponseItem(
            response_id=successor.id, item_code=item.item_code, value_json=item.value_json,
        ))
    session.flush()
    _audit(
        session,
        study_id=visit.subject.study_id,
        site_id=visit.subject.site_id,
        actor_user_id=actor_user_id,
        action="amend",
        target_type="questionnaire_response",
        target_id=successor.id,
        payload={"supersedes_response_id": prior.id, "reason": reason.strip()},
    )
    return successor

