"""계획서 버전별 eCRF 초안, 개정 비교, 입력 보존.

추출 결과는 제안이다. 규칙 묶음을 ACTIVE로 바꾸지 않고 창 검증도 켜지 않는다.
모의 승인은 SIMULATED_APPROVAL로만 기록한다.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.clinical_support import (
    AuditEventChain,
    DataLockState,
    EcrfEntry,
    EcrfSchemaVersion,
    ProtocolDocument,
    StudySite,
    StudySubject,
    StudyVisit,
)
from services.clinical_protocol_rules import osdi_form_visits, visit_assessments
from services.clinical_records import ClinicalRecordError, _AUDIT_GENESIS, _audit, _require_site_member

GENESIS = _AUDIT_GENESIS
CatalogBuilder = Callable[[str], tuple[list[dict], list[dict]]]


def _canonical(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _osdi_visits(version: str) -> list[str]:
    form = osdi_form_visits()
    if version == "1.3":
        return form["v13_form_visits"].split(",")
    if version == "1.10":
        return form["form_visits"].split(",")
    raise ClinicalRecordError("지원하는 계획서 버전은 1.3과 1.10입니다.")


def _field(**kwargs) -> dict:
    row = {
        "required": False,
        "repeated": False,
        "repeat_count": 1,
        "laterality": None,
        "proposal": True,
        "enforced": False,
        "window_check": False,
        "extraction_method": "reviewed_rule_pack",
        "confidence": "source_metadata",
        "value_kind": "number",
        "allows_not_applicable": False,
    }
    row.update(kwargs)
    return row


def _medi_des_001(version: str) -> tuple[list[dict], list[dict]]:
    """MEDI-DES-001만의 카탈로그. 다른 연구 식별자에는 쓰이지 않는다."""
    osdi_visits = _osdi_visits(version)
    grid = visit_assessments()
    shared = [visit for visit in ("V1", "V2", "V3", "V4", "V6") if grid[visit]["TBUT"]]
    fields = [
        _field(logical_field_id="SUBJID", form_code="SCREENING", code="SUBJID", unit="code", value_kind="text", visits=["V1"], section="11.2.1", protocol_version=version),
        _field(logical_field_id="TBUT-OD-REPEAT", form_code="TBUT", code="TBUT", laterality="OD", unit="s", repeated=True, repeat_count=3, visits=shared, section="10.2.4.12 (1)", protocol_version=version),
        _field(logical_field_id="TBUT-OD-AVG", form_code="TBUT", code="TBUT", laterality="OD", unit="s", visits=shared, section="10.2.4.12 (1)", protocol_version=version),
        _field(logical_field_id="TBUT-OS-REPEAT", form_code="TBUT", code="TBUT", laterality="OS", unit="s", repeated=True, repeat_count=3, visits=shared, section="10.2.4.12 (1)", protocol_version=version),
        _field(logical_field_id="TBUT-OS-AVG", form_code="TBUT", code="TBUT", laterality="OS", unit="s", visits=shared, section="10.2.4.12 (1)", protocol_version=version),
        _field(logical_field_id="SCHIRMER-OD", form_code="SCHIRMER", code="SCHIRMER", laterality="OD", unit="mm/5min", visits=shared, section="10.2.4.12 (2)", protocol_version=version),
        _field(logical_field_id="SCHIRMER-OS", form_code="SCHIRMER", code="SCHIRMER", laterality="OS", unit="mm/5min", visits=shared, section="10.2.4.12 (2)", protocol_version=version),
        _field(logical_field_id="OSDI-SCORE", form_code="OSDI", code="OSDI", unit="score", visits=osdi_visits, section="부록 1", protocol_version=version),
    ]
    for index in range(1, 13):
        fields.append(_field(
            logical_field_id=f"OSQ{index}",
            form_code="OSDI",
            code="OSDI",
            unit="score",
            visits=osdi_visits,
            section="부록 1",
            protocol_version=version,
            allows_not_applicable=index >= 6,
            proposed_range=[0, 4],
        ))
    forms = [
        {"form_code": "SCREENING", "coverage": "FIELD", "source": "11.2.1", "proposal": True},
        {"form_code": "OSDI", "coverage": "FIELD", "source": "부록 1", "proposal": True},
        {"form_code": "TBUT", "coverage": "FIELD", "source": "10.2.4.12 (1)", "proposal": True},
        {"form_code": "SCHIRMER", "coverage": "FIELD", "source": "10.2.4.12 (2)", "proposal": True},
        {"form_code": "VISIT_ASSESSMENTS", "coverage": "SCHEDULE_ONLY", "source": "11.1, 11.2", "proposal": True, "note": "FCSS와 LGCSS는 방문 칸만 있고 문항 필드는 없다."},
        {"form_code": "INCLUSION_EXCLUSION", "coverage": "NAME_ONLY", "source": None, "proposal": True},
        {"form_code": "MEDICAL_HISTORY", "coverage": "NAME_ONLY", "source": None, "proposal": True},
        {"form_code": "CM", "coverage": "STAGED_NO_STABLE_KEY", "source": "10.3, 11.2", "proposal": True},
        {"form_code": "CT", "coverage": "STAGED_NO_STABLE_KEY", "source": "10.3, 11.2", "proposal": True},
        {"form_code": "AE", "coverage": "STAGED_NO_STABLE_KEY", "source": "15", "proposal": True},
        {"form_code": "DE", "coverage": "STAGED_NO_STABLE_KEY", "source": "15", "proposal": True},
        {"form_code": "EX", "coverage": "STAGED_NO_STABLE_KEY", "source": "11.2.4", "proposal": True, "note": "Visit 4 처치는 UNRESOLVED"},
        {"form_code": "DS", "coverage": "STAGED_NO_STABLE_KEY", "source": "11.2", "proposal": True},
    ]
    return fields, forms


_CATALOGS: dict[str, CatalogBuilder] = {"MEDI-DES-001": _medi_des_001}


def register_form_catalog(identifier: str, builder: CatalogBuilder) -> None:
    _CATALOGS[identifier] = builder


def _schema_body(identifier: str, version: str) -> dict:
    builder = _CATALOGS.get(identifier)
    if builder is None:
        fields, forms = [], [{"form_code": "UNCONFIGURED", "coverage": "NO_CATALOG", "proposal": True, "source": None}]
    else:
        fields, forms = builder(version)
    return {
        "protocol_identifier": identifier,
        "protocol_version": version,
        "proposal": True,
        "rules_active": False,
        "window_check": False,
        "unresolved": [
            "FORMAL_SIGNATURE",
            "WINDOW_3_VS_7",
            "VISIT4_TREATMENT",
            "OSDI_ROUNDING",
        ],
        "forms": forms,
        "fields": fields,
    }


def _member(session: Session, study_id: str, site_id: str, user_id: str) -> None:
    _require_site_member(session, site_id, user_id)
    site = session.get(StudySite, site_id)
    if site is None or site.study_id != study_id:
        raise ClinicalRecordError("사이트가 이 연구에 속하지 않습니다.")


def register_protocol(
    session: Session,
    *,
    study_id: str,
    site_id: str,
    actor_user_id: str,
    actor_role: str,
    version_label: str,
    source_sha256: str,
    document_date: str,
    source_present: bool,
    source_reference: str,
    protocol_identifier: str = "MEDI-DES-001",
    parent_document_id: str | None = None,
    request_id: str = "protocol-ecrf",
) -> ProtocolDocument:
    _member(session, study_id, site_id, actor_user_id)
    if len(source_sha256) != 64:
        raise ClinicalRecordError("원본 SHA-256이 필요합니다.")
    if protocol_identifier == "MEDI-DES-001":
        _osdi_visits(version_label)
    elif protocol_identifier not in _CATALOGS:
        raise ClinicalRecordError("이 연구 계획서의 양식 카탈로그가 없습니다.")
    row = ProtocolDocument(
        study_id=study_id,
        protocol_identifier=protocol_identifier,
        version_label=version_label,
        source_sha256=source_sha256,
        document_date=document_date,
        source_reference=source_reference,
        source_present=source_present,
        extraction_status="NOT_STARTED",
        review_status="UNREVIEWED",
        approval_status="UNRESOLVED",
        activation_status="INACTIVE",
        simulated_approval=False,
        parent_document_id=parent_document_id,
        effective_date=None,
    )
    session.add(row)
    session.flush()
    _chain(
        session,
        study_id=study_id,
        site_id=site_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action="protocol_registered",
        target_type="protocol_document",
        target_id=row.id,
        protocol_version=version_label,
        schema_version_id=None,
        reason="계획서 원본 등록",
        payload={"sha256": source_sha256, "source_present": source_present},
        request_id=request_id,
    )
    return row


def generate_draft(
    session: Session,
    *,
    study_id: str,
    site_id: str,
    actor_user_id: str,
    actor_role: str,
    document_id: str,
) -> EcrfSchemaVersion:
    _member(session, study_id, site_id, actor_user_id)
    document = session.get(ProtocolDocument, document_id)
    if document is None or document.study_id != study_id:
        raise ClinicalRecordError("계획서 버전이 없습니다.")
    body = _schema_body(document.protocol_identifier, document.version_label)
    raw = _canonical(body)
    schema = EcrfSchemaVersion(
        document_id=document.id,
        study_id=study_id,
        schema_hash=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        status="DRAFT",
        definition_json=raw,
    )
    document.extraction_status = "EXTRACTED"
    session.add(schema)
    session.flush()
    _chain(
        session,
        study_id=study_id,
        site_id=site_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action="ecrf_generated",
        target_type="ecrf_schema",
        target_id=schema.id,
        protocol_version=document.version_label,
        schema_version_id=schema.id,
        reason="규칙 묶음에서 eCRF 초안 생성",
        payload={"schema_hash": schema.schema_hash, "proposal": True},
    )
    return schema


def review_schema(session: Session, *, study_id: str, site_id: str, actor_user_id: str, actor_role: str, schema_id: str) -> EcrfSchemaVersion:
    _member(session, study_id, site_id, actor_user_id)
    schema = session.get(EcrfSchemaVersion, schema_id)
    if schema is None or schema.study_id != study_id:
        raise ClinicalRecordError("eCRF 초안이 없습니다.")
    document = session.get(ProtocolDocument, schema.document_id)
    document.review_status = "REVIEWED"
    _chain(
        session,
        study_id=study_id,
        site_id=site_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action="schema_reviewed",
        target_type="ecrf_schema",
        target_id=schema.id,
        protocol_version=document.version_label,
        schema_version_id=schema.id,
        reason="초안 검토",
        payload={"schema_hash": schema.schema_hash},
    )
    return schema


def simulate_approval(session: Session, *, study_id: str, site_id: str, actor_user_id: str, actor_role: str, document_id: str) -> ProtocolDocument:
    _member(session, study_id, site_id, actor_user_id)
    document = session.get(ProtocolDocument, document_id)
    if document is None or document.study_id != study_id:
        raise ClinicalRecordError("계획서 버전이 없습니다.")
    document.approval_status = "SIMULATED_APPROVAL"
    document.simulated_approval = True
    _chain(
        session,
        study_id=study_id,
        site_id=site_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action="simulated_approval",
        target_type="protocol_document",
        target_id=document.id,
        protocol_version=document.version_label,
        schema_version_id=None,
        reason="개발용 모의 승인. 실제 서명이 아니다.",
        payload={"approval_status": "SIMULATED_APPROVAL", "rules_active": False},
    )
    return document


def activate_schema(session: Session, *, study_id: str, site_id: str, actor_user_id: str, actor_role: str, schema_id: str) -> EcrfSchemaVersion:
    _member(session, study_id, site_id, actor_user_id)
    schema = session.get(EcrfSchemaVersion, schema_id)
    if schema is None or schema.study_id != study_id:
        raise ClinicalRecordError("eCRF 초안이 없습니다.")
    before = schema.definition_json
    document = session.get(ProtocolDocument, schema.document_id)
    if document.approval_status != "SIMULATED_APPROVAL":
        raise ClinicalRecordError("모의 승인 전 스키마는 활성화할 수 없습니다.")
    schema.status = "ACTIVE"
    document.activation_status = "ACTIVE"
    document.effective_date = document.document_date
    if schema.definition_json != before:
        raise ClinicalRecordError("스키마 본문은 바꿀 수 없습니다.")
    _chain(
        session,
        study_id=study_id,
        site_id=site_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action="schema_activated",
        target_type="ecrf_schema",
        target_id=schema.id,
        protocol_version=document.version_label,
        schema_version_id=schema.id,
        reason="개발용 스키마 활성화",
        payload={"schema_hash": schema.schema_hash, "simulated": True},
    )
    return schema


def amendment_report(session: Session, *, study_id: str, earlier_id: str, later_id: str) -> dict:
    earlier = session.get(EcrfSchemaVersion, earlier_id)
    later = session.get(EcrfSchemaVersion, later_id)
    if earlier is None or later is None or earlier.study_id != study_id or later.study_id != study_id:
        raise ClinicalRecordError("비교할 스키마가 없습니다.")
    left = {row["logical_field_id"]: row for row in json.loads(earlier.definition_json)["fields"]}
    right = {row["logical_field_id"]: row for row in json.loads(later.definition_json)["fields"]}
    later_body = json.loads(later.definition_json)
    changes = []
    for logical_id in sorted(set(left) | set(right)):
        old = left.get(logical_id)
        new = right.get(logical_id)
        if old is None and new is not None:
            kind = "ADDED"
        elif old is not None and new is None:
            kind = "REMOVED"
        elif old["visits"] != new["visits"]:
            kind = "CHANGED_VISIT_SCHEDULE"
        elif old["unit"] != new["unit"]:
            kind = "CHANGED_UNIT"
        else:
            kind = "UNCHANGED"
        changes.append({
            "logical_field_id": logical_id,
            "classification": kind,
            "earlier_visits": None if old is None else old["visits"],
            "later_visits": None if new is None else new["visits"],
        })
    return {
        "earlier_schema_id": earlier.id,
        "later_schema_id": later.id,
        "earlier_hash": earlier.schema_hash,
        "later_hash": later.schema_hash,
        "changes": changes,
        "unresolved": later_body["unresolved"],
        "ambiguous_forms": [
            row["form_code"] for row in later_body.get("forms", [])
            if row.get("coverage") in {"NAME_ONLY", "STAGED_NO_STABLE_KEY", "SCHEDULE_ONLY", "NO_CATALOG"}
        ],
        "overwrites_history": False,
    }


def dry_run_mapping(report: dict) -> dict:
    return {
        "writes": 0,
        "mappings": [
            {"logical_field_id": row["logical_field_id"], "action": "preserve"}
            for row in report["changes"]
        ],
        "rollback": "이전 스키마 입력은 개정 행으로 남고 새 스키마는 별도 ID다.",
    }


def rollback_plan(report: dict) -> dict:
    return {
        "writes": 0,
        "keep_schema_id": report["earlier_schema_id"],
        "later_schema_id": report["later_schema_id"],
        "steps": ["새 스키마 입력을 지우지 않는다.", "이전 스키마 ID로 계속 조회한다."],
    }


def save_entry(
    session: Session,
    *,
    study_id: str,
    site_id: str,
    actor_user_id: str,
    actor_role: str,
    schema_id: str,
    subject_id: str,
    visit_id: str,
    logical_field_id: str,
    value_number: float | None,
    value_text: str | None,
    repeat_index: int = 1,
    reason: str | None = None,
) -> EcrfEntry:
    _member(session, study_id, site_id, actor_user_id)
    schema = session.get(EcrfSchemaVersion, schema_id)
    if schema is None or schema.study_id != study_id:
        raise ClinicalRecordError("eCRF 스키마가 없습니다.")
    body = json.loads(schema.definition_json)
    field = next((row for row in body["fields"] if row["logical_field_id"] == logical_field_id), None)
    if field is None:
        raise ClinicalRecordError("필드가 이 스키마에 없습니다.")
    visit = session.get(StudyVisit, visit_id)
    subject = session.get(StudySubject, subject_id)
    if visit is None or subject is None or visit.subject_id != subject.id or subject.site_id != site_id:
        raise ClinicalRecordError("방문이 이 사이트에 없습니다.")
    if visit.visit_code not in field["visits"]:
        raise ClinicalRecordError("이 계획서 버전에서 해당 방문의 필드가 아닙니다.")
    not_applicable = field.get("allows_not_applicable") and value_text == "NA" and value_number is None
    if field.get("value_kind") == "number" and value_number is None and not not_applicable:
        raise ClinicalRecordError("수치 필드입니다.")
    if field.get("value_kind") == "text" and not (value_text or "").strip():
        raise ClinicalRecordError("텍스트 필드입니다.")
    if field["repeated"] and repeat_index not in {1, 2, 3}:
        raise ClinicalRecordError("반복 측정은 1부터 3까지입니다.")
    _assert_unlocked(session, study_id=study_id, visit_id=visit_id)
    revision = session.scalar(
        select(func.coalesce(func.max(EcrfEntry.revision), 0)).where(
            EcrfEntry.visit_id == visit_id,
            EcrfEntry.schema_version_id == schema.id,
            EcrfEntry.logical_field_id == logical_field_id,
            EcrfEntry.repeat_index == repeat_index,
        )
    )
    entry = EcrfEntry(
        study_id=study_id,
        site_id=site_id,
        subject_id=subject_id,
        visit_id=visit_id,
        schema_version_id=schema.id,
        protocol_version=body["protocol_version"],
        logical_field_id=logical_field_id,
        repeat_index=repeat_index,
        revision=int(revision) + 1,
        value_number=value_number,
        value_text=value_text,
        unit=field["unit"],
        record_status="draft" if schema.status != "ACTIVE" else "recorded",
        source="manual",
        reason=reason,
        created_by=actor_user_id,
    )
    session.add(entry)
    session.flush()
    _chain(
        session,
        study_id=study_id,
        site_id=site_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action="ecrf_entry",
        target_type="ecrf_entry",
        target_id=entry.id,
        protocol_version=entry.protocol_version,
        schema_version_id=schema.id,
        reason=reason or "합성 입력",
        payload={
            "logical_field_id": logical_field_id,
            "revision": entry.revision,
            "value_protected": True,
        },
    )
    return entry


def render_schema(schema: EcrfSchemaVersion) -> dict:
    body = json.loads(schema.definition_json)
    return {
        "schema_id": schema.id,
        "status": schema.status,
        "schema_hash": schema.schema_hash,
        "protocol_version": body["protocol_version"],
        "fields": body["fields"],
        "forms": body.get("forms", []),
        "unresolved": body["unresolved"],
    }


def verify_chain(session: Session, study_id: str) -> dict:
    rows = session.scalars(
        select(AuditEventChain).where(AuditEventChain.study_id == study_id).order_by(AuditEventChain.chain_seq)
    ).all()
    linked = {row.previous_hash for row in rows}
    return {"count": len(rows), "has_genesis": any(row.previous_hash == GENESIS for row in rows), "linked": len(linked)}


def _assert_unlocked(session: Session, *, study_id: str, visit_id: str) -> None:
    state = session.scalar(
        select(DataLockState).where(
            DataLockState.study_id == study_id,
            DataLockState.target_id == visit_id,
            DataLockState.state.in_(("LOCKED", "FROZEN", "SIGNED")),
        )
    )
    if state is not None:
        raise ClinicalRecordError("잠긴 방문에는 입력할 수 없습니다.")


def _chain(
    session: Session,
    *,
    study_id: str,
    site_id: str | None,
    actor_user_id: str,
    actor_role: str,
    action: str,
    target_type: str,
    target_id: str,
    protocol_version: str | None,
    schema_version_id: str | None,
    reason: str,
    payload: dict,
    request_id: str = "protocol-ecrf",
) -> None:
    _audit(
        session,
        study_id=study_id,
        site_id=site_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action=action,
        target_type=target_type,
        target_id=target_id,
        payload=payload,
        request_id=request_id,
        reason=reason,
        protocol_version=protocol_version,
        schema_version_id=schema_version_id,
        link_chain=True,
    )


def list_entries(session: Session, *, schema_id: str) -> list[EcrfEntry]:
    return list(session.scalars(select(EcrfEntry).where(EcrfEntry.schema_version_id == schema_id)))
