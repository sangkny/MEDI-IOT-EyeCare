"""설문 초안, 채점, 통계, 아키텍처 증거 API."""
from __future__ import annotations

from pathlib import Path

from auth.policy import policy_require
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from services.architecture_evidence import build_architecture_evidence, validate_evidence
from services.clinical_records import ClinicalRecordError
from services.improvement_loop import list_findings, record_finding, transition_finding
from services.questionnaire_engine import (
    compare_questionnaire_versions,
    finalize_questionnaire_response,
    generate_osdi_draft,
    open_questionnaire_response,
    questionnaire_stats,
    record_questionnaire_item,
    score_osdi_response,
)

router = APIRouter()
page_router = APIRouter()
_PAGE = Path(__file__).resolve().parent.parent / "static" / "questionnaire" / "index.html"


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


class DraftBody(BaseModel):
    site_id: str = Field(max_length=36)
    document_id: str = Field(max_length=36)


class ResponseBody(BaseModel):
    version_id: str
    visit_id: str


class ItemBody(BaseModel):
    item_code: str
    value: object
    reason: str | None = None


class FindingBody(BaseModel):
    finding_code: str
    source_analyzer: str = "svg-analyzer"
    source_version: str
    module_id: str
    severity: str
    evidence: dict
    proposed_correction: str
    reproduction: str | None = None


class TransitionBody(BaseModel):
    next_state: str
    decision: str | None = None
    decision_reason: str | None = None
    fix_ref: str | None = None
    test_evidence: str | None = None
    reanalysis_outcome: str | None = None


@page_router.get("/questionnaire")
def questionnaire_page():
    return FileResponse(_PAGE, media_type="text/html; charset=utf-8")


@router.post("/studies/{study_id}/questionnaire-drafts")
async def draft(
    study_id: str, body: DraftBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_questionnaire_manage")),
):
    return await _call(
        db, generate_osdi_draft, study_id=study_id, site_id=body.site_id,
        actor_user_id=_uid(user), actor_role=_role(user), document_id=body.document_id,
    )


@router.post("/questionnaire-engine/responses")
async def start(
    body: ResponseBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_questionnaire_manage")),
):
    row = await _call(
        db, open_questionnaire_response, version_id=body.version_id, visit_id=body.visit_id,
        actor_user_id=_uid(user), actor_role=_role(user),
    )
    return {"id": row.id, "status": row.status, "version_id": row.version_id}


@router.post("/questionnaire-engine/responses/{response_id}/items")
async def item(
    response_id: str, body: ItemBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_questionnaire_manage")),
):
    row = await _call(
        db, record_questionnaire_item, response_id=response_id, actor_user_id=_uid(user),
        actor_role=_role(user), item_code=body.item_code, value=body.value, reason=body.reason,
    )
    return {"id": row.id, "item_code": row.item_code}


@router.post("/questionnaire-engine/responses/{response_id}/finalize")
async def finalize(
    response_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_questionnaire_manage")),
):
    row = await _call(
        db, finalize_questionnaire_response, response_id=response_id,
        actor_user_id=_uid(user), actor_role=_role(user),
    )
    return {"id": row.id, "status": row.status}


@router.post("/questionnaire-engine/responses/{response_id}/score")
async def score(
    response_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_questionnaire_manage")),
):
    row = await _call(
        db, score_osdi_response, response_id=response_id,
        actor_user_id=_uid(user), actor_role=_role(user),
    )
    return {
        "id": row.id,
        "scoring_version": row.scoring_version,
        "answered_count": row.answered_count,
        "not_applicable_count": row.not_applicable_count,
        "blank_count": row.blank_count,
        "status": row.status,
        "has_calculated_score": row.calculated_score is not None,
    }


@router.get("/studies/{study_id}/questionnaire-stats")
async def stats(
    study_id: str,
    site_id: str = Query(max_length=36),
    definition_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_observation_read")),
):
    return await _call(
        db, questionnaire_stats, study_id=study_id, site_id=site_id,
        actor_user_id=_uid(user), definition_id=definition_id,
    )


@router.get("/studies/{study_id}/questionnaire-amendments")
async def amend(
    study_id: str,
    earlier_id: str = Query(),
    later_id: str = Query(),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_observation_read")),
):
    return await _call(
        db, compare_questionnaire_versions, study_id=study_id,
        earlier_id=earlier_id, later_id=later_id,
    )


@router.get("/architecture-evidence")
async def evidence(
    user: dict = Depends(policy_require("medi-iot", "clinical_audit_read")),
):
    payload = build_architecture_evidence()
    errors = validate_evidence(payload)
    if errors:
        raise HTTPException(status_code=500, detail={"errors": errors})
    return payload


@router.post("/improvement-findings")
async def create_finding(
    body: FindingBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_protocol_manage")),
):
    row = await _call(
        db, record_finding, finding_code=body.finding_code, source_analyzer=body.source_analyzer,
        source_version=body.source_version, module_id=body.module_id, severity=body.severity,
        evidence=body.evidence, proposed_correction=body.proposed_correction,
        reproduction=body.reproduction,
    )
    return {"id": row.id, "state": row.state}


@router.post("/improvement-findings/{finding_id}/transitions")
async def move_finding(
    finding_id: str, body: TransitionBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_protocol_manage")),
):
    row = await _call(
        db, transition_finding, finding_id=finding_id, next_state=body.next_state,
        decision=body.decision, decision_reason=body.decision_reason, fix_ref=body.fix_ref,
        test_evidence=body.test_evidence, reanalysis_outcome=body.reanalysis_outcome,
    )
    return {"id": row.id, "state": row.state, "decision": row.decision}


@router.get("/improvement-findings")
async def findings(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_audit_read")),
):
    rows = await _call(db, list_findings)
    return [
        {"id": row.id, "finding_code": row.finding_code, "module_id": row.module_id, "state": row.state}
        for row in rows
    ]
