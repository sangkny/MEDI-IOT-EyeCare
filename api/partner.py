"""SaMD 파트너 엔터프라이즈 API — API Key · 과금 · FHIR/HL7."""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from services.partner_service import (
    authenticate_partner,
    partner_dashboard,
    register_partner,
    run_partner_analyze,
)

log = logging.getLogger("api.partner")
router = APIRouter()


class PartnerRegisterRequest(BaseModel):
    partner_id: str = Field(..., min_length=2, max_length=64)
    name: str = Field(..., min_length=1, max_length=200)
    plan: Literal["trial", "standard", "enterprise"] = "trial"
    cost_per_analysis: float = Field(default=0.05, ge=0.0, le=100.0)


class PartnerRegisterResponse(BaseModel):
    partner_id: str
    name: str
    plan: str
    api_key: str
    message: str = "API key는 이 응답에서만 표시됩니다. 안전하게 보관하세요."


class PartnerAnalyzeRequest(BaseModel):
    partner_id: str
    api_key: str | None = Field(
        default=None,
        description="본문 또는 X-API-Key 헤더",
    )
    image_base64: str
    analysis_type: Literal["fundus"] = "fundus"
    return_format: Literal["json", "fhir", "hl7"] = "json"
    lang: Literal["ko", "en"] = "ko"
    patient_id: str | None = None
    include_heatmap: bool = False


async def _resolve_api_key(
    body_key: str | None,
    header_key: str | None,
) -> str:
    key = (header_key or body_key or "").strip()
    if not key:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="api_key required (body or X-API-Key header)",
        )
    return key


@router.post(
    "/register",
    response_model=PartnerRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="파트너 등록 + API Key 발급",
)
async def partner_register(
    body: PartnerRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> PartnerRegisterResponse:
    try:
        account, api_key = await register_partner(
            db,
            partner_id=body.partner_id,
            name=body.name,
            plan=body.plan,
            cost_per_analysis=body.cost_per_analysis,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return PartnerRegisterResponse(
        partner_id=account.partner_id,
        name=account.name,
        plan=account.plan,
        api_key=api_key,
    )


@router.post("/analyze", summary="파트너 안저 분석 (과금 기록)")
async def partner_analyze(
    body: PartnerAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    api_key = await _resolve_api_key(body.api_key, x_api_key)
    try:
        account = await authenticate_partner(
            db, partner_id=body.partner_id, api_key=api_key
        )
    except PermissionError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    try:
        return await run_partner_analyze(
            db,
            account,
            image_base64=body.image_base64,
            analysis_type=body.analysis_type,
            return_format=body.return_format,
            lang=body.lang,
            patient_id=body.patient_id,
            include_heatmap=body.include_heatmap,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"CNN unavailable: {exc}",
        ) from exc
    except Exception as exc:
        log.exception("partner analyze failed")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc)[:200],
        ) from exc


@router.get(
    "/dashboard/{partner_id}",
    summary="파트너 사용량·비용 대시보드",
)
async def partner_dashboard_endpoint(
    partner_id: str,
    db: AsyncSession = Depends(get_db),
    x_api_key: str = Header(..., alias="X-API-Key"),
):
    try:
        account = await authenticate_partner(
            db, partner_id=partner_id, api_key=x_api_key
        )
    except PermissionError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return await partner_dashboard(db, account)
