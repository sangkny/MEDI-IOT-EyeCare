"""증례 대시보드 화면과 읽기 전용 집계."""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Annotated

from auth.policy import policy_require
from fastapi import APIRouter, Depends, HTTPException, Path as ApiPath, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from services.clinical_case_dashboard import build_case_dashboard, validate_case_export
from services.clinical_records import ClinicalRecordError

router = APIRouter()
page_router = APIRouter()
_PAGE = Path(__file__).resolve().parent.parent / "static" / "clinical-dashboard" / "index.html"


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


class CaseValidationBody(BaseModel):
    site_id: str
    content_base64: str = ""


@page_router.get("/clinical-dashboard", response_class=FileResponse)
async def case_dashboard_page() -> FileResponse:
    if not _PAGE.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="증례 대시보드 화면이 없습니다.")
    return FileResponse(_PAGE, media_type="text/html; charset=utf-8")


@router.get("/studies/{study_id}/case-dashboard")
async def get_case_dashboard(
    study_id: Annotated[str, ApiPath(max_length=36)],
    site_id: Annotated[str, Query(max_length=36)],
    subject_code: str | None = Query(default=None, max_length=64),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_observation_read")),
) -> dict:
    return await _call(
        db,
        build_case_dashboard,
        study_id=study_id,
        site_id=site_id,
        actor_user_id=_uid(user),
        subject_code=subject_code,
    )


@router.post("/studies/{study_id}/case-validations")
async def post_case_validation(
    study_id: Annotated[str, ApiPath(max_length=36)],
    body: CaseValidationBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_observation_read")),
) -> dict:
    content = b""
    if body.content_base64:
        try:
            content = base64.b64decode(body.content_base64, validate=True)
        except Exception as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="파일을 읽을 수 없습니다.") from exc
    return await _call(
        db,
        validate_case_export,
        study_id=study_id,
        site_id=body.site_id,
        actor_user_id=_uid(user),
        content=content or None,
    )
