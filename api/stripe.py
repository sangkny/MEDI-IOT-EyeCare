"""MEDI Stripe 결제 게이트웨이 라우트 (D R2 Day 1).

ADK / CoOps 와 동일 패턴 — ``medi_stripe`` 인스턴스로 위임.

엔드포인트 (모두 ``/api/v1/billing/stripe/...``):
    - GET  /status              — env 토글 + supported events 진단
    - POST /checkout            — 인증 사용자가 plan_code 로 Checkout Session 생성
    - POST /webhook             — Stripe 가 호출 (raw body + Stripe-Signature)
    - POST /portal              — Customer Portal session (B-7 R2)
    - POST /admin/plan-mapping  — admin 이 plan ↔ stripe_price_id 매핑 등록
    - GET  /admin/plan-mapping/{plan_code} — admin 이 매핑 조회
"""
from __future__ import annotations

import logging

from auth.dependencies import current_user_strict, require_role
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from saas.schemas import (
    StripeCheckoutRequest,
    StripeCheckoutResponse,
    StripeMeteredUsageRequest,
    StripeMeteredUsageResponse,
    StripePlanMappingOut,
    StripePlanMappingRequest,
    StripePortalRequest,
    StripePortalResponse,
    StripeStatusResponse,
    StripeWebhookResponse,
)
from saas.stripe_service import (
    SUPPORTED_EVENTS,
    StripeDisabled,
    StripeSignatureError,
)
from services.billing import medi_stripe

log = logging.getLogger("api.medi.stripe")
router = APIRouter()


@router.get("/status", response_model=StripeStatusResponse)
async def stripe_status() -> StripeStatusResponse:
    cfg = medi_stripe.config
    return StripeStatusResponse(
        enabled=cfg.enabled,
        public_key=cfg.public_key if cfg.enabled else None,
        supported_events=sorted(SUPPORTED_EVENTS),
    )


@router.post("/checkout", response_model=StripeCheckoutResponse)
async def create_checkout(
    body: StripeCheckoutRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(current_user_strict),
) -> StripeCheckoutResponse:
    try:
        session = await medi_stripe.create_checkout_session(
            db,
            user_id=str(user.get("user_id", "")),
            plan_code=body.plan_code,
            success_url=body.success_url,
            cancel_url=body.cancel_url,
            allow_promotion_codes=body.allow_promotion_codes,
            promotion_code=body.promotion_code,
            coupon_id=body.coupon_id,
        )
    except StripeDisabled as e:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)
        ) from e
    except ValueError as e:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    return StripeCheckoutResponse(session_id=session["id"], url=session["url"])


@router.post("/webhook", response_model=StripeWebhookResponse)
async def stripe_webhook(
    request: Request, db: AsyncSession = Depends(get_db)
) -> StripeWebhookResponse:
    if not medi_stripe.is_enabled():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe 가 비활성 상태 (STRIPE_ENABLED=0)",
        )
    raw = await request.body()
    sig = request.headers.get("stripe-signature")
    try:
        event = medi_stripe.parse_event(raw, sig)
    except StripeSignatureError as e:
        log.warning("Stripe webhook 서명 검증 실패: %s", e)
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    result = await medi_stripe.handle_event(db, event)
    return StripeWebhookResponse(**result)


@router.post("/portal", response_model=StripePortalResponse)
async def create_portal(
    body: StripePortalRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(current_user_strict),
) -> StripePortalResponse:
    try:
        session = await medi_stripe.create_portal_session(
            db,
            user_id=str(user.get("user_id", "")),
            return_url=body.return_url,
            flow=body.flow,
        )
    except StripeDisabled as e:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)
        ) from e
    except ValueError as e:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    return StripePortalResponse(session_id=session["id"], url=session["url"])


@router.post("/metered-usage", response_model=StripeMeteredUsageResponse)
async def submit_metered_usage(
    body: StripeMeteredUsageRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(current_user_strict),
) -> StripeMeteredUsageResponse:
    try:
        result = await medi_stripe.submit_metered_usage(
            db,
            user_id=str(user.get("user_id", "")),
            quantity=body.quantity,
            action=body.action,
            timestamp=body.timestamp,
        )
    except StripeDisabled as e:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)
        ) from e
    except ValueError as e:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    return StripeMeteredUsageResponse(**result)


@router.post("/admin/plan-mapping", response_model=StripePlanMappingOut)
async def admin_set_plan_mapping(
    body: StripePlanMappingRequest,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_role("admin")),
) -> StripePlanMappingOut:
    try:
        await medi_stripe.set_plan_mapping(
            db, plan_code=body.plan_code, stripe_price_id=body.stripe_price_id
        )
    except ValueError as e:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    return StripePlanMappingOut(
        plan_code=body.plan_code, stripe_price_id=body.stripe_price_id
    )


@router.get(
    "/admin/plan-mapping/{plan_code}", response_model=StripePlanMappingOut
)
async def admin_get_plan_mapping(
    plan_code: str,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(require_role("admin")),
) -> StripePlanMappingOut:
    mapping = await medi_stripe.get_plan_mapping(db, plan_code=plan_code)
    if mapping is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"plan '{plan_code}' has no Stripe price mapping",
        )
    return StripePlanMappingOut(
        plan_code=plan_code, stripe_price_id=mapping.stripe_price_id
    )
