"""인증된 임상 지원 API. 레거시 무인증 환자 라우트와 분리한다."""
from __future__ import annotations

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
from services.clinical_quality import run_quality_rules
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


def _fail(exc: ClinicalRecordError) -> HTTPException:
    text = str(exc)
    if "구성원" in text:
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
