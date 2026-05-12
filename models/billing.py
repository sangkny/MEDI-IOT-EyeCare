"""MEDI SaaS billing models — shared.saas factory 위임 (D R2 Day 1).

ADK / CoOps 와 동일 schema, prefix=``medi_``. Stripe sidecar 도 함께 생성 — 임상 SaaS
가격이 enterprise 친화적 ($299/$999/$2,999) 이므로 Stripe 결제는 처음부터 인프라 준비.
"""
from __future__ import annotations

from database import Base
from saas import make_billing_models, make_stripe_models

(
    BillingPlan,
    BillingSubscription,
    BillingUsageRecord,
    BillingMonthlyUserUsage,
) = make_billing_models(Base, table_prefix="medi_")

StripePlanMapping, StripeSubscription = make_stripe_models(
    Base, table_prefix="medi_"
)

__all__ = [
    "BillingPlan",
    "BillingSubscription",
    "BillingUsageRecord",
    "BillingMonthlyUserUsage",
    "StripePlanMapping",
    "StripeSubscription",
]
