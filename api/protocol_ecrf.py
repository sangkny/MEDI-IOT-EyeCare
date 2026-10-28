"""계획서 버전과 eCRF 초안 API."""
from __future__ import annotations

from pathlib import Path

from auth.policy import policy_require
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from services.clinical_records import ClinicalRecordError
from services.protocol_ecrf import (  # noqa: E402
    activate_schema,
    amendment_report,
    dry_run_mapping,
    generate_draft,
    list_entries,
    register_protocol,
    render_schema,
    review_schema,
    save_entry,
    simulate_approval,
    verify_chain,
    _member,
)
from models.clinical_support import ClinicalQuery, DataLockState, EcrfSchemaVersion

router = APIRouter()
page_router = APIRouter()
_PAGE = Path(__file__).resolve().parent.parent / "static" / "protocol-ecrf" / "index.html"


def _fail(exc: ClinicalRecordError) -> HTTPException:
    text = str(exc)
    code = status.HTTP_403_FORBIDDEN if "구성원" in text or "권한" in text else status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=code, detail=text)


async def _call(db: AsyncSession, fn, **kwargs):
    try:
        return await db.run_sync(lambda sync: fn(sync, **kwargs))
    except ClinicalRecordError as exc:
        raise _fail(exc) from exc


def _uid(user: dict) -> str:
    return str(user["user_id"])


def _role(user: dict) -> str:
    return str(user.get("role") or "unknown")


class RegisterBody(BaseModel):
    site_id: str = Field(max_length=36)
    version_label: str = Field(max_length=16)
    source_sha256: str = Field(min_length=64, max_length=64)
    document_date: str = Field(max_length=16)
    source_present: bool
    source_reference: str = Field(max_length=200)
    parent_document_id: str | None = None


class SchemaBody(BaseModel):
    site_id: str = Field(max_length=36)


class EntryBody(BaseModel):
    site_id: str = Field(max_length=36)
    schema_id: str = Field(max_length=36)
    subject_id: str = Field(max_length=36)
    visit_id: str = Field(max_length=36)
    logical_field_id: str = Field(max_length=64)
    value_number: float | None = None
    value_text: str | None = None
    repeat_index: int = 1
    reason: str | None = None


class CompareBody(BaseModel):
    earlier_id: str
    later_id: str


@page_router.get("/protocol-ecrf")
def protocol_page():
    return FileResponse(_PAGE, media_type="text/html; charset=utf-8")


@router.post("/studies/{study_id}/protocol-documents")
async def register(
    study_id: str,
    body: RegisterBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_protocol_manage")),
):
    row = await _call(
        db, register_protocol,
        study_id=study_id, site_id=body.site_id, actor_user_id=_uid(user), actor_role=_role(user),
        version_label=body.version_label, source_sha256=body.source_sha256,
        document_date=body.document_date, source_present=body.source_present,
        source_reference=body.source_reference, parent_document_id=body.parent_document_id,
    )
    return {"id": row.id, "approval_status": row.approval_status, "extraction_status": row.extraction_status}


@router.post("/studies/{study_id}/protocol-documents/{document_id}/draft")
async def draft(
    study_id: str,
    document_id: str,
    body: SchemaBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_protocol_manage")),
):
    schema = await _call(
        db, generate_draft,
        study_id=study_id, site_id=body.site_id, actor_user_id=_uid(user),
        actor_role=_role(user), document_id=document_id,
    )
    return render_schema(schema)


@router.post("/studies/{study_id}/ecrf-schemas/{schema_id}/review")
async def review(
    study_id: str, schema_id: str, body: SchemaBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_protocol_manage")),
):
    schema = await _call(
        db, review_schema, study_id=study_id, site_id=body.site_id,
        actor_user_id=_uid(user), actor_role=_role(user), schema_id=schema_id,
    )
    return {"id": schema.id, "status": schema.status}


@router.post("/studies/{study_id}/protocol-documents/{document_id}/simulated-approval")
async def approve(
    study_id: str, document_id: str, body: SchemaBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_protocol_manage")),
):
    row = await _call(
        db, simulate_approval, study_id=study_id, site_id=body.site_id,
        actor_user_id=_uid(user), actor_role=_role(user), document_id=document_id,
    )
    return {"id": row.id, "approval_status": row.approval_status, "simulated_approval": row.simulated_approval}


@router.post("/studies/{study_id}/ecrf-schemas/{schema_id}/activate")
async def activate(
    study_id: str, schema_id: str, body: SchemaBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_protocol_manage")),
):
    schema = await _call(
        db, activate_schema, study_id=study_id, site_id=body.site_id,
        actor_user_id=_uid(user), actor_role=_role(user), schema_id=schema_id,
    )
    return {"id": schema.id, "status": schema.status}


@router.post("/studies/{study_id}/ecrf-amendments")
async def amend(
    study_id: str, body: CompareBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_observation_read")),
):
    report = await _call(
        db, amendment_report, study_id=study_id, earlier_id=body.earlier_id, later_id=body.later_id,
    )
    report["dry_run"] = dry_run_mapping(report)
    return report


@router.post("/studies/{study_id}/ecrf-entries")
async def enter(
    study_id: str, body: EntryBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_observation_create")),
):
    entry = await _call(
        db, save_entry, study_id=study_id, site_id=body.site_id, actor_user_id=_uid(user),
        actor_role=_role(user), schema_id=body.schema_id, subject_id=body.subject_id,
        visit_id=body.visit_id, logical_field_id=body.logical_field_id,
        value_number=body.value_number, value_text=body.value_text,
        repeat_index=body.repeat_index, reason=body.reason,
    )
    return {
        "id": entry.id,
        "protocol_version": entry.protocol_version,
        "schema_version_id": entry.schema_version_id,
        "revision": entry.revision,
        "record_status": entry.record_status,
        "unit": entry.unit,
    }


@router.get("/studies/{study_id}/ecrf-schemas/{schema_id}")
async def read_schema(
    study_id: str, schema_id: str, site_id: str = Query(max_length=36),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_observation_read")),
):
    def _load(sync, study_id, schema_id, site_id, user_id):
        _member(sync, study_id, site_id, user_id)
        schema = sync.get(EcrfSchemaVersion, schema_id)
        if schema is None or schema.study_id != study_id:
            raise ClinicalRecordError("eCRF 스키마가 없습니다.")
        payload = render_schema(schema)
        payload["entries"] = [
            {
                "logical_field_id": row.logical_field_id,
                "repeat_index": row.repeat_index,
                "revision": row.revision,
                "protocol_version": row.protocol_version,
                "record_status": row.record_status,
            }
            for row in list_entries(sync, schema_id=schema.id)
        ]
        payload["audit"] = verify_chain(sync, study_id)
        names = set(inspect(sync.get_bind()).get_table_names())
        if "data_lock_states" in names:
            payload["locks"] = [
                {"target_type": row.target_type, "state": row.state}
                for row in sync.scalars(select(DataLockState).where(DataLockState.site_id == site_id))
            ]
        else:
            payload["locks"] = []
        if "clinical_queries" in names:
            payload["queries"] = dict(sync.execute(
                select(ClinicalQuery.status, func.count()).where(ClinicalQuery.site_id == site_id).group_by(ClinicalQuery.status)
            ).all())
        else:
            payload["queries"] = {}
        return payload
    return await _call(db, _load, study_id=study_id, schema_id=schema_id, site_id=site_id, user_id=_uid(user))
