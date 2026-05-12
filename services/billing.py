"""MEDI SaaS billing service — shared.BillingService 위임 (D R2 Day 1).

ADK / CoOps 와 동일 패턴. ``medi_billing`` + ``medi_stripe`` 인스턴스 export.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from models.billing import (
    BillingMonthlyUserUsage,
    BillingPlan,
    BillingSubscription,
    BillingUsageRecord,
    StripePlanMapping,
    StripeSubscription,
)
from saas import BillingService, StripeConfig, StripeService
from saas.helpers import (
    DEFAULT_FREE_PLAN_CODE,
    current_year_month,
    parse_allowed_models,
    usage_snapshot_dict,
)

medi_billing = BillingService(
    plan_cls=BillingPlan,
    subscription_cls=BillingSubscription,
    usage_record_cls=BillingUsageRecord,
    monthly_usage_cls=BillingMonthlyUserUsage,
    default_free_code=DEFAULT_FREE_PLAN_CODE,
    service_name="medi",
)

medi_stripe_config = StripeConfig.from_env(prefix="MEDI_")
medi_stripe = StripeService(
    config=medi_stripe_config,
    billing=medi_billing,
    plan_mapping_cls=StripePlanMapping,
    stripe_subscription_cls=StripeSubscription,
)


# ── 함수형 wrapper (다른 모듈이 단순 import 로 사용) ────────────


async def get_plan_by_code(db: AsyncSession, code: str):
    return await medi_billing.get_plan_by_code(db, code)


async def list_active_plans(db: AsyncSession) -> list[Any]:
    return await medi_billing.list_active_plans(db)


async def get_active_subscription(db: AsyncSession, user_id: str):
    return await medi_billing.get_active_subscription(db, user_id)


async def get_or_create_active_subscription(
    db: AsyncSession, user_id: str
) -> tuple[Any, Any]:
    return await medi_billing.get_or_create_active_subscription(db, user_id)


async def switch_subscription(
    db: AsyncSession, user_id: str, new_plan_code: str
) -> tuple[Any, Any, str | None]:
    return await medi_billing.switch_subscription(db, user_id, new_plan_code)


async def get_or_create_monthly_usage(
    db: AsyncSession, user_id: str, *, year_month: str | None = None
):
    return await medi_billing.get_or_create_monthly_usage(
        db, user_id, year_month=year_month
    )


__all__ = [
    "DEFAULT_FREE_PLAN_CODE",
    "medi_billing",
    "medi_stripe",
    "medi_stripe_config",
    "current_year_month",
    "get_plan_by_code",
    "list_active_plans",
    "get_active_subscription",
    "get_or_create_active_subscription",
    "switch_subscription",
    "get_or_create_monthly_usage",
    "parse_allowed_models",
    "usage_snapshot_dict",
]
