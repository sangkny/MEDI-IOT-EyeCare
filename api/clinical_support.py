"""인증된 임상 지원 API. 레거시 무인증 환자 라우트와 분리한다."""
from __future__ import annotations

import base64
from datetime import date

from auth.policy import policy_require
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from schemas.clinical_support import (
    ObservationRecord,
    StudyRecord,
    SubjectRecord,
    VisitRecord,
)
from services.clinical_explore import list_study_visits, subject_visit_history
from services.clinical_import import confirm_import, preview_import
from services.clinical_lock import (
    apply_lock,
    approve_unlock,
    evaluate_lock_readiness,
    list_clinical_audit,
    list_lock_history,
    reject_unlock,
    request_lock,
    request_unlock,
)
from services.clinical_monitoring import (
    ai_monitoring_handoff,
    compute_monitoring_indicators,
    list_monitoring_indicators,
)
from services.clinical_quality import list_quality_findings, run_quality_rules, validate_after_entry
from services.clinical_queries import (
    assign_query,
    correct_from_query,
    create_query,
    create_query_from_finding,
    get_query,
    list_queries,
    list_query_history,
    reopen_query,
    resolve_query,
    respond_to_query,
)
from services.clinical_readiness import approve_protocol_definition, register_protocol_definition
from services.clinical_records import (
    ClinicalRecordError,
    add_site,
    add_site_member,
    assign_visit_form,
    correct_observation,
    correct_response,
    create_draft_observation,
    create_study,
    define_questionnaire,
    enroll_subject,
    finalize_observation,
    finalize_response,
    get_authorized_subject,
    get_effective_observation,
    get_study,
    list_authorized_studies,
    list_observation_history,
    list_site_members,
    list_sites_for_member,
    list_subject_visits,
    list_visible_subjects,
    open_visit,
    publish_questionnaire_version,
    save_response_item,
    start_response,
    update_draft_observation,
)

router = APIRouter()


class StudyBody(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    study_kind: str = "dataset"
    protocol_version: str | None = None


class SiteBody(BaseModel):
    site_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)


class MemberBody(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    role: str = Field(min_length=1, max_length=32)


class SubjectBody(BaseModel):
    study_id: str
    site_id: str
    subject_code: str = Field(min_length=1, max_length=64)
    enrolled_on: date | None = None


class VisitBody(BaseModel):
    subject_id: str
    visit_code: str = Field(min_length=1, max_length=64)
    occurred_on: date
    repeat_no: int = Field(default=1, ge=1)
    window_id: str | None = None


class DraftBody(BaseModel):
    visit_id: str
    code: str = Field(min_length=1, max_length=64)
    laterality: str = "NA"
    method: str = "NA"
    repeat_index: int = Field(default=1, ge=1)
    value_number: float | None = None
    value_text: str | None = None
    unit: str | None = None


class DraftUpdate(BaseModel):
    value_number: float | None = None
    value_text: str | None = None
    unit: str | None = None


class CorrectionBody(BaseModel):
    reason: str = Field(min_length=1)
    value_number: float | None = None
    value_text: str | None = None
    unit: str | None = None


class QuestionnaireBody(BaseModel):
    study_id: str
    code: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)


class VersionBody(BaseModel):
    version_number: int = Field(ge=1)
    items_json: str


class FormAssignmentBody(BaseModel):
    study_id: str
    visit_code: str
    definition_id: str


class ResponseBody(BaseModel):
    version_id: str
    visit_id: str


class ItemBody(BaseModel):
    item_code: str
    value_json: str


class ReasonBody(BaseModel):
    reason: str = Field(min_length=1)


class QualityRunBody(BaseModel):
    scope: str = "study"
    scope_id: str | None = None


class QueryBody(BaseModel):
    study_id: str
    category: str = Field(min_length=1, max_length=64)
    severity: str = Field(min_length=1, max_length=16)
    description: str = Field(min_length=1)
    subject_id: str | None = None
    visit_id: str | None = None
    definition_id: str | None = None
    observation_id: str | None = None
    finding_id: str | None = None
    assigned_user_id: str | None = None
    assigned_role: str | None = None


class QueryAssignBody(BaseModel):
    reason: str = Field(min_length=1)
    assigned_user_id: str | None = None
    assigned_role: str | None = None


class QueryResponseBody(BaseModel):
    body: str = Field(min_length=1)


class ReadinessBody(BaseModel):
    study_id: str
    target_type: str = Field(min_length=1, max_length=32)
    target_id: str


class LockTargetBody(BaseModel):
    study_id: str
    target_type: str = Field(min_length=1, max_length=32)
    target_id: str
    reason: str = Field(min_length=1)


class UnlockDecisionBody(BaseModel):
    reason: str = Field(min_length=1)


class ProtocolBody(BaseModel):
    requirements: dict


def _query_payload(row) -> dict:
    return {
        "id": row.id,
        "study_id": row.study_id,
        "site_id": row.site_id,
        "subject_id": row.subject_id,
        "visit_id": row.visit_id,
        "definition_id": row.definition_id,
        "observation_id": row.observation_id,
        "finding_id": row.finding_id,
        "category": row.category,
        "severity": row.severity,
        "description": row.description,
        "status": row.status,
        "assigned_user_id": row.assigned_user_id,
        "assigned_role": row.assigned_role,
    }


def _fail(exc: ClinicalRecordError) -> HTTPException:
    text = str(exc)
    if "구성원" in text or "권한" in text:
        code = status.HTTP_403_FORBIDDEN
    elif any(token in text for token in ("가 없습니다", "이 없습니다", "은 없습니다", "에 없습니다")):
        code = status.HTTP_404_NOT_FOUND
    else:
        code = status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=code, detail=text)


async def _call(db: AsyncSession, fn, **kwargs):
    try:
        return await db.run_sync(lambda sync: fn(sync, **kwargs))
    except ClinicalRecordError as exc:
        raise _fail(exc) from exc


def _uid(user: dict) -> str:
    return str(user["user_id"])


@router.get("/templates/medi-des-001")
async def medi_des_template(_user: dict = Depends(policy_require("medi-iot", "clinical_study_read"))) -> dict:
    return {
        "code": "MEDI-DES-001",
        "status": "BLOCKED_PENDING_SOURCE",
        "indication": "dry-eye",
        "design": ["prospective", "randomized", "double-masked", "sham-controlled"],
        "target_enrollment": 60,
        "regimen_note": "주 2회, 8주는 확인된 일반 설명이며 승인된 Visit 일정이 아니다.",
        "visit_windows": None,
        "questionnaires": None,
        "allocation": None,
    }


@router.post("/studies", response_model=StudyRecord, status_code=status.HTTP_201_CREATED)
async def post_study(
    body: StudyBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_study_manage")),
) -> StudyRecord:
    row = await _call(db, create_study, code=body.code, name=body.name, study_kind=body.study_kind,
                      protocol_version=body.protocol_version, actor_user_id=_uid(user))
    return StudyRecord.model_validate(row)


@router.get("/studies", response_model=list[StudyRecord])
async def get_studies(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_study_read")),
) -> list[StudyRecord]:
    rows = await _call(db, list_authorized_studies, user_id=_uid(user))
    return [StudyRecord.model_validate(row) for row in rows]


@router.get("/studies/{study_id}", response_model=StudyRecord)
async def get_one_study(
    study_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_study_read")),
) -> StudyRecord:
    def _load(sync, user_id: str):
        from services.clinical_records import _require_study_member
        row = get_study(sync, study_id)
        if row is None:
            raise ClinicalRecordError("연구가 없습니다.")
        _require_study_member(sync, study_id, user_id)
        return row
    row = await _call(db, _load, user_id=_uid(user))
    return StudyRecord.model_validate(row)


@router.get("/studies/{study_id}/sites")
async def get_sites(
    study_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_study_read")),
) -> list[dict]:
    rows = await _call(db, list_sites_for_member, study_id=study_id, user_id=_uid(user))
    return [{"id": row.id, "site_code": row.site_code, "name": row.name} for row in rows]


@router.post("/studies/{study_id}/sites", status_code=status.HTTP_201_CREATED)
async def post_site(
    study_id: str,
    body: SiteBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_study_manage")),
) -> dict:
    row = await _call(
        db, add_site, study_id=study_id, site_code=body.site_code, name=body.name, actor_user_id=_uid(user),
    )
    return {"id": row.id, "site_code": row.site_code}


@router.get("/studies/{study_id}/members")
async def get_members(
    study_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_study_read")),
) -> list[dict]:
    rows = await _call(db, list_site_members, study_id=study_id, user_id=_uid(user))
    return [{"id": row.id, "site_id": row.site_id, "user_id": row.user_id, "role": row.role} for row in rows]


@router.post("/sites/{site_id}/members", status_code=status.HTTP_201_CREATED)
async def post_member(
    site_id: str,
    body: MemberBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_study_manage")),
) -> dict:
    row = await _call(
        db, add_site_member, site_id=site_id, user_id=body.user_id, role=body.role, actor_user_id=_uid(user),
    )
    return {"id": row.id, "user_id": row.user_id, "role": row.role}


@router.post("/subjects", response_model=SubjectRecord, status_code=status.HTTP_201_CREATED)
async def post_subject(
    body: SubjectBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_subject_manage")),
) -> SubjectRecord:
    row = await _call(
        db, enroll_subject, study_id=body.study_id, site_id=body.site_id,
        subject_code=body.subject_code, enrolled_on=body.enrolled_on, actor_user_id=_uid(user),
    )
    return SubjectRecord.model_validate(row)


@router.get("/subjects/{subject_id}", response_model=SubjectRecord)
async def get_subject(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_subject_read")),
) -> SubjectRecord:
    row = await _call(db, get_authorized_subject, subject_id=subject_id, user_id=_uid(user))
    return SubjectRecord.model_validate(row)


@router.get("/studies/{study_id}/subjects", response_model=list[SubjectRecord])
async def get_subjects(
    study_id: str,
    site_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_subject_read")),
) -> list[SubjectRecord]:
    rows = await _call(
        db, list_visible_subjects, study_id=study_id, user_id=_uid(user), site_id=site_id,
    )
    return [SubjectRecord.model_validate(row) for row in rows]


@router.post("/visits", response_model=VisitRecord, status_code=status.HTTP_201_CREATED)
async def post_visit(
    body: VisitBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_visit_manage")),
) -> VisitRecord:
    row = await _call(
        db, open_visit, subject_id=body.subject_id, visit_code=body.visit_code,
        occurred_on=body.occurred_on, repeat_no=body.repeat_no, window_id=body.window_id,
        actor_user_id=_uid(user),
    )
    return VisitRecord.model_validate(row)


@router.get("/subjects/{subject_id}/visits", response_model=list[VisitRecord])
async def get_visits(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_visit_read")),
) -> list[VisitRecord]:
    rows = await _call(db, list_subject_visits, subject_id=subject_id, user_id=_uid(user))
    return [VisitRecord.model_validate(row) for row in rows]


@router.post("/observations/drafts", response_model=ObservationRecord, status_code=status.HTTP_201_CREATED)
async def post_draft(
    body: DraftBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_observation_create")),
) -> ObservationRecord:
    row = await _call(
        db, create_draft_observation, visit_id=body.visit_id, code=body.code,
        laterality=body.laterality, method=body.method, repeat_index=body.repeat_index,
        value_number=body.value_number, value_text=body.value_text, unit=body.unit,
        recorded_by=_uid(user), actor_user_id=_uid(user),
    )
    return ObservationRecord.model_validate(row)


@router.patch("/observations/{observation_id}", response_model=ObservationRecord)
async def patch_draft(
    observation_id: str,
    body: DraftUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_observation_create")),
) -> ObservationRecord:
    changes = body.model_dump(exclude_unset=True)
    row = await _call(
        db, update_draft_observation, observation_id=observation_id,
        actor_user_id=_uid(user), **changes,
    )
    return ObservationRecord.model_validate(row)


@router.post("/observations/{observation_id}/finalize", response_model=ObservationRecord)
async def post_finalize(
    observation_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_observation_finalize")),
) -> ObservationRecord:
    row = await _call(db, finalize_observation, observation_id=observation_id, actor_user_id=_uid(user))
    return ObservationRecord.model_validate(row)


@router.get("/observations/effective", response_model=ObservationRecord)
async def get_effective(
    visit_id: str,
    code: str,
    laterality: str = "NA",
    method: str = "NA",
    repeat_index: int = 1,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_observation_read")),
) -> ObservationRecord:
    def _load(sync, user_id: str):
        from models.clinical_support import StudyVisit
        visit = sync.get(StudyVisit, visit_id)
        if visit is None:
            raise ClinicalRecordError("Visit 가 없습니다.")
        from services.clinical_records import _require_site_member
        _require_site_member(sync, visit.subject.site_id, user_id)
        row = get_effective_observation(
            sync, visit_id=visit_id, code=code, laterality=laterality,
            method=method, repeat_index=repeat_index,
        )
        if row is None:
            raise ClinicalRecordError("유효 관찰이 없습니다.")
        return row
    row = await _call(db, _load, user_id=_uid(user))
    return ObservationRecord.model_validate(row)


@router.post("/observations/{observation_id}/corrections", response_model=ObservationRecord)
async def post_correction(
    observation_id: str,
    body: CorrectionBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_observation_correct")),
) -> ObservationRecord:
    row = await _call(
        db, correct_observation, observation_id=observation_id, actor_user_id=_uid(user),
        reason=body.reason, value_number=body.value_number, value_text=body.value_text, unit=body.unit,
    )
    return ObservationRecord.model_validate(row)


@router.get("/observations/history", response_model=list[ObservationRecord])
async def get_history(
    visit_id: str,
    code: str,
    laterality: str = "NA",
    method: str = "NA",
    repeat_index: int = Query(default=1),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_observation_read")),
) -> list[ObservationRecord]:
    def _load(sync, user_id: str):
        from models.clinical_support import StudyVisit
        from services.clinical_records import _require_site_member
        visit = sync.get(StudyVisit, visit_id)
        if visit is None:
            raise ClinicalRecordError("Visit 가 없습니다.")
        _require_site_member(sync, visit.subject.site_id, user_id)
        return list_observation_history(
            sync, visit_id=visit_id, code=code, laterality=laterality,
            method=method, repeat_index=repeat_index,
        )
    rows = await _call(db, _load, user_id=_uid(user))
    return [ObservationRecord.model_validate(row) for row in rows]


@router.post("/questionnaires", status_code=status.HTTP_201_CREATED)
async def post_questionnaire(
    body: QuestionnaireBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_questionnaire_manage")),
) -> dict:
    row = await _call(
        db, define_questionnaire, study_id=body.study_id, code=body.code, title=body.title,
        actor_user_id=_uid(user),
    )
    return {"id": row.id, "code": row.code}


@router.post("/questionnaires/{definition_id}/versions", status_code=status.HTTP_201_CREATED)
async def post_version(
    definition_id: str,
    body: VersionBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_questionnaire_manage")),
) -> dict:
    row = await _call(
        db, publish_questionnaire_version, definition_id=definition_id,
        version_number=body.version_number, items_json=body.items_json, actor_user_id=_uid(user),
    )
    return {"id": row.id, "version_number": row.version_number, "content_hash": row.content_hash}


@router.post("/visit-forms", status_code=status.HTTP_201_CREATED)
async def post_form_assignment(
    body: FormAssignmentBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_questionnaire_manage")),
) -> dict:
    row = await _call(
        db, assign_visit_form, study_id=body.study_id, visit_code=body.visit_code,
        definition_id=body.definition_id, actor_user_id=_uid(user),
    )
    return {"id": row.id, "visit_code": row.visit_code}


@router.post("/questionnaire-responses", status_code=status.HTTP_201_CREATED)
async def post_response(
    body: ResponseBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_questionnaire_manage")),
) -> dict:
    row = await _call(
        db, start_response, version_id=body.version_id, visit_id=body.visit_id,
        recorded_by=_uid(user), actor_user_id=_uid(user),
    )
    return {"id": row.id, "status": row.status, "version_id": row.version_id}


@router.post("/questionnaire-responses/{response_id}/items")
async def post_item(
    response_id: str,
    body: ItemBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_questionnaire_manage")),
) -> dict:
    row = await _call(
        db, save_response_item, response_id=response_id, actor_user_id=_uid(user),
        item_code=body.item_code, value_json=body.value_json,
    )
    return {"id": row.id, "item_code": row.item_code}


@router.post("/questionnaire-responses/{response_id}/finalize")
async def post_response_finalize(
    response_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_questionnaire_manage")),
) -> dict:
    row = await _call(db, finalize_response, response_id=response_id, actor_user_id=_uid(user))
    return {"id": row.id, "status": row.status, "finalized_by": row.finalized_by}


@router.post("/questionnaire-responses/{response_id}/corrections")
async def post_response_correction(
    response_id: str,
    body: ReasonBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_questionnaire_manage")),
) -> dict:
    row = await _call(
        db, correct_response, response_id=response_id, actor_user_id=_uid(user), reason=body.reason,
    )
    return {"id": row.id, "status": row.status, "supersedes_response_id": row.supersedes_response_id}


@router.post("/studies/{study_id}/quality-runs")
async def post_quality(
    study_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_study_manage")),
) -> dict:
    def _run(sync, user_id: str):
        from services.clinical_records import _require_study_member
        _require_study_member(sync, study_id, user_id)
        rows = run_quality_rules(sync, study_id=study_id, actor_user_id=user_id)
        return [row.id for row in rows]
    ids = await _call(db, _run, user_id=_uid(user))
    return {"finding_ids": ids}


@router.get("/studies/{study_id}/quality-findings")
async def get_findings(
    study_id: str,
    status_filter: str | None = Query(default=None, alias="status"),
    severity: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_quality_read")),
) -> list[dict]:
    rows = await _call(
        db, list_quality_findings, study_id=study_id, actor_user_id=_uid(user),
        status=status_filter, severity=severity,
    )
    return [
        {
            "id": row.id,
            "rule_id": row.rule_id,
            "rule_version": row.rule_version,
            "severity": row.rule.severity,
            "status": row.status,
            "message_code": row.message_code,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "source_revision": row.source_revision,
            "evaluation_scope": row.evaluation_scope,
            "evaluated_at": row.evaluated_at.isoformat() if row.evaluated_at else None,
        }
        for row in rows
    ]


@router.post("/studies/{study_id}/quality-validations")
async def post_quality_validation(
    study_id: str,
    body: QualityRunBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_quality_execute")),
) -> dict:
    def _run(sync, user_id: str):
        from services.clinical_records import _require_study_member
        _require_study_member(sync, study_id, user_id)
        rows = run_quality_rules(
            sync, study_id=study_id, actor_user_id=user_id,
            scope=body.scope, scope_id=body.scope_id, trigger="manual",
        )
        return [row.id for row in rows]
    return {"finding_ids": await _call(db, _run, user_id=_uid(user))}


@router.post("/visits/{visit_id}/quality-runs")
async def post_visit_quality(
    visit_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_quality_execute")),
) -> dict:
    rows = await _call(db, validate_after_entry, visit_id=visit_id, actor_user_id=_uid(user))
    return {"finding_ids": [row.id for row in rows]}


@router.get("/queries")
async def get_queries(
    study_id: str,
    site_id: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    severity: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_query_read")),
) -> list[dict]:
    rows = await _call(
        db, list_queries, study_id=study_id, actor_user_id=_uid(user),
        site_id=site_id, status=status_filter, severity=severity,
    )
    return [_query_payload(row) for row in rows]


@router.get("/queries/{query_id}")
async def get_one_query(
    query_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_query_read")),
) -> dict:
    return _query_payload(await _call(db, get_query, query_id=query_id, actor_user_id=_uid(user)))


@router.post("/queries", status_code=status.HTTP_201_CREATED)
async def post_query(
    body: QueryBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_query_create")),
) -> dict:
    row = await _call(db, create_query, actor_user_id=_uid(user), **body.model_dump())
    return _query_payload(row)


@router.post("/findings/{finding_id}/queries", status_code=status.HTTP_201_CREATED)
async def post_query_from_finding(
    finding_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_query_create")),
) -> dict:
    row = await _call(
        db, create_query_from_finding, finding_id=finding_id, actor_user_id=_uid(user),
    )
    return _query_payload(row)


@router.post("/queries/{query_id}/responses")
async def post_query_response(
    query_id: str,
    body: QueryResponseBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_query_respond")),
) -> dict:
    row = await _call(
        db, respond_to_query, query_id=query_id, actor_user_id=_uid(user), body=body.body,
    )
    return _query_payload(row)


@router.post("/queries/{query_id}/assignments")
async def post_query_assignment(
    query_id: str,
    body: QueryAssignBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_query_review")),
) -> dict:
    row = await _call(
        db, assign_query, query_id=query_id, actor_user_id=_uid(user),
        reason=body.reason, assigned_user_id=body.assigned_user_id, assigned_role=body.assigned_role,
    )
    return _query_payload(row)


@router.post("/queries/{query_id}/resolutions")
async def post_query_resolution(
    query_id: str,
    body: ReasonBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_query_review")),
) -> dict:
    row = await _call(
        db, resolve_query, query_id=query_id, actor_user_id=_uid(user), reason=body.reason,
    )
    return _query_payload(row)


@router.post("/queries/{query_id}/reopens")
async def post_query_reopen(
    query_id: str,
    body: ReasonBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_query_review")),
) -> dict:
    row = await _call(
        db, reopen_query, query_id=query_id, actor_user_id=_uid(user), reason=body.reason,
    )
    return _query_payload(row)


@router.get("/queries/{query_id}/history")
async def get_query_history(
    query_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_query_read")),
) -> list[dict]:
    rows = await _call(db, list_query_history, query_id=query_id, actor_user_id=_uid(user))
    return [
        {
            "id": row.id,
            "from_status": row.from_status,
            "to_status": row.to_status,
            "actor_user_id": row.actor_user_id,
            "reason": row.reason,
            "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
        }
        for row in rows
    ]


@router.post("/queries/{query_id}/corrections")
async def post_query_correction(
    query_id: str,
    body: CorrectionBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_observation_correct")),
) -> dict:
    row = await _call(
        db, correct_from_query, query_id=query_id, actor_user_id=_uid(user),
        reason=body.reason, value_number=body.value_number, value_text=body.value_text, unit=body.unit,
    )
    return {"id": row.id, "revision": row.revision, "record_status": row.record_status}


def _lock_body(row) -> dict:
    return {
        "id": row.id,
        "study_id": row.study_id,
        "site_id": row.site_id,
        "scope": row.scope,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "state": row.state,
        "version": row.version,
        "target_revision": row.target_revision,
    }


@router.get("/readiness")
async def get_readiness(
    study_id: str,
    target_type: str,
    target_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_readiness_read")),
) -> dict:
    return await _call(
        db, evaluate_lock_readiness, study_id=study_id, target_type=target_type,
        target_id=target_id, actor_user_id=_uid(user),
    )


@router.post("/locks/readiness")
async def post_lock_readiness(
    body: ReadinessBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_readiness_read")),
) -> dict:
    return await _call(
        db, evaluate_lock_readiness, study_id=body.study_id, target_type=body.target_type,
        target_id=body.target_id, actor_user_id=_uid(user),
    )


@router.post("/locks/requests")
async def post_lock_request(
    body: LockTargetBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_lock_request")),
) -> dict:
    row = await _call(
        db, request_lock, study_id=body.study_id, target_type=body.target_type,
        target_id=body.target_id, actor_user_id=_uid(user), reason=body.reason,
    )
    return _lock_body(row)


@router.post("/locks/applications")
async def post_lock_application(
    body: LockTargetBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_lock_apply")),
) -> dict:
    row = await _call(
        db, apply_lock, study_id=body.study_id, target_type=body.target_type,
        target_id=body.target_id, actor_user_id=_uid(user), reason=body.reason,
    )
    return _lock_body(row)


@router.post("/locks/unlock-requests", status_code=status.HTTP_201_CREATED)
async def post_unlock_request(
    body: LockTargetBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_unlock_request")),
) -> dict:
    row = await _call(
        db, request_unlock, study_id=body.study_id, target_type=body.target_type,
        target_id=body.target_id, actor_user_id=_uid(user), reason=body.reason,
    )
    return {
        "id": row.id,
        "status": row.status,
        "requesting_user_id": row.requesting_user_id,
        "lock_state_at_request": row.lock_state_at_request,
        "target_type": row.target_type,
        "target_id": row.target_id,
    }


@router.post("/locks/unlock-requests/{request_id}/approvals")
async def post_unlock_approval(
    request_id: str,
    body: UnlockDecisionBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_unlock_approve")),
) -> dict:
    row = await _call(
        db, approve_unlock, request_row_id=request_id, actor_user_id=_uid(user), reason=body.reason,
    )
    return _lock_body(row)


@router.post("/locks/unlock-requests/{request_id}/rejections")
async def post_unlock_rejection(
    request_id: str,
    body: UnlockDecisionBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_unlock_approve")),
) -> dict:
    row = await _call(
        db, reject_unlock, request_row_id=request_id, actor_user_id=_uid(user), reason=body.reason,
    )
    return _lock_body(row)


@router.get("/locks/history")
async def get_lock_history(
    study_id: str,
    target_type: str | None = None,
    target_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_lock_read")),
) -> list[dict]:
    rows = await _call(
        db, list_lock_history, study_id=study_id, actor_user_id=_uid(user),
        target_type=target_type, target_id=target_id,
    )
    return [
        {
            "id": row.id,
            "action": row.action,
            "from_state": row.from_state,
            "to_state": row.to_state,
            "actor_user_id": row.actor_user_id,
            "reason": row.reason,
            "request_id": row.request_id,
            "target_revision": row.target_revision,
            "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
        }
        for row in rows
    ]


@router.get("/audits")
async def get_audits(
    study_id: str,
    target_type: str | None = None,
    target_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_audit_read")),
) -> list[dict]:
    rows = await _call(
        db, list_clinical_audit, study_id=study_id, actor_user_id=_uid(user),
        target_type=target_type, target_id=target_id,
    )
    return [
        {
            "id": row.id,
            "actor_user_id": row.actor_user_id,
            "action": row.action,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "site_id": row.site_id,
            "previous_state": row.previous_state,
            "new_state": row.new_state,
            "reason": row.reason,
            "request_id": row.request_id,
            "target_revision": row.target_revision,
            "payload_hash": row.payload_hash,
            "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
        }
        for row in rows
    ]


@router.post("/studies/{study_id}/protocol-definitions", status_code=status.HTTP_201_CREATED)
async def post_protocol(
    study_id: str,
    body: ProtocolBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_protocol_manage")),
) -> dict:
    row = await _call(
        db, register_protocol_definition, study_id=study_id, actor_user_id=_uid(user),
        requirements=body.requirements,
    )
    return {"id": row.id, "status": row.status, "version_number": row.version_number}


@router.post("/protocol-definitions/{definition_id}/approvals")
async def post_protocol_approval(
    definition_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_protocol_manage")),
) -> dict:
    row = await _call(
        db, approve_protocol_definition, definition_id=definition_id, actor_user_id=_uid(user),
    )
    return {"id": row.id, "status": row.status, "version_number": row.version_number}


@router.post("/studies/{study_id}/monitoring-indicators")
async def post_monitoring(
    study_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_monitor_execute")),
) -> dict:
    rows = await _call(
        db, compute_monitoring_indicators, study_id=study_id, actor_user_id=_uid(user),
    )
    return {
        "indicators": [
            {
                "id": row.id,
                "indicator_code": row.indicator_code,
                "status": row.status,
                "handoff": ai_monitoring_handoff(row),
            }
            for row in rows
        ]
    }


class ImportBody(BaseModel):
    study_id: str
    site_id: str
    filename: str = "upload.xlsx"
    content_base64: str
    source_system: str = "external-edc"


def _import_bytes(encoded: str) -> bytes:
    try:
        return base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="파일을 읽을 수 없습니다.") from exc


@router.post("/imports/previews")
async def post_import_preview(
    body: ImportBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_observation_read")),
) -> dict:
    return await _call(
        db,
        preview_import,
        study_id=body.study_id,
        site_id=body.site_id,
        actor_user_id=_uid(user),
        content=_import_bytes(body.content_base64),
    )


@router.post("/imports/confirmations", status_code=status.HTTP_201_CREATED)
async def post_import_confirmation(
    body: ImportBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_observation_create")),
) -> dict:
    return await _call(
        db,
        confirm_import,
        study_id=body.study_id,
        site_id=body.site_id,
        actor_user_id=_uid(user),
        filename=body.filename,
        content=_import_bytes(body.content_base64),
        source_system=body.source_system,
    )


@router.get("/subjects/{subject_id}/visit-history")
async def get_subject_visit_history(
    subject_id: str,
    occurred_from: date | None = None,
    occurred_to: date | None = None,
    site_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_subject_read")),
) -> dict:
    return await _call(
        db,
        subject_visit_history,
        subject_id=subject_id,
        actor_user_id=_uid(user),
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        site_id=site_id,
    )


@router.get("/studies/{study_id}/visit-index")
async def get_visit_index(
    study_id: str,
    site_id: str | None = None,
    occurred_from: date | None = None,
    occurred_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_visit_read")),
) -> list[dict]:
    return await _call(
        db,
        list_study_visits,
        study_id=study_id,
        actor_user_id=_uid(user),
        site_id=site_id,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
    )


@router.get("/studies/{study_id}/monitoring-indicators")
async def get_monitoring(
    study_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_monitor_read")),
) -> list[dict]:
    rows = await _call(
        db, list_monitoring_indicators, study_id=study_id, actor_user_id=_uid(user),
    )
    return [
        {"id": row.id, "indicator_code": row.indicator_code, "status": row.status}
        for row in rows
    ]
