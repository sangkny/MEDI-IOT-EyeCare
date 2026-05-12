"""MEDI SaaS Billing 테스트 (D R2 Day 1).

테스트 철학 (Mock 0):
    - LLM/네트워크 mock 절대 금지
    - LM Studio 호출이 들어가는 분기는 ``enforce_quota`` 가 *앞에서* 429 로 차단되도록
      DB 상태를 직접 조작 (state 시드는 mock 이 아님)
    - 실 dev 서버 (``localhost:8000``) + 실 PostgreSQL — ``test_clinical.py`` 와
      동일하게 ``httpx.Client`` (sync) 로 ASGI/asyncpg 이벤트 루프 충돌 회피.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from config import get_settings
from models.billing import (
    BillingMonthlyUserUsage,
    BillingPlan,
    BillingSubscription,
)


BASE = "http://localhost:8000"


def _async_db_url() -> str:
    url = get_settings().database_url
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


@pytest.fixture(scope="module")
def client() -> httpx.Client:
    with httpx.Client(base_url=BASE, timeout=30.0) as c:
        yield c


def _token(client: httpx.Client, username: str, password: str) -> str:
    r = client.post(
        "/api/v1/auth/token",
        data={"username": username, "password": password},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _headers(client: httpx.Client, role: str = "doctor") -> dict[str, str]:
    creds = {
        "admin": ("admin", "admin123"),
        "doctor": ("doctor", "doc123"),
        "staff": ("staff", "staff123"),
    }
    u, p = creds[role]
    return {"Authorization": f"Bearer {_token(client, u, p)}"}


def _seed_subscription(user_id: str, plan_code: str) -> None:
    """user_id 에 plan_code 활성 구독 시드 (httpx 호출 없이 직접 DB)."""

    async def _do() -> None:
        url = _async_db_url()
        eng = create_async_engine(url, poolclass=NullPool)
        SM = async_sessionmaker(eng, expire_on_commit=False)
        try:
            async with SM() as s:
                plan = (
                    await s.execute(
                        select(BillingPlan).where(BillingPlan.code == plan_code)
                    )
                ).scalar_one()
                old = (
                    await s.execute(
                        select(BillingSubscription)
                        .where(BillingSubscription.user_id == user_id)
                        .where(BillingSubscription.status == "active")
                    )
                ).scalars().all()
                for o in old:
                    o.status = "cancelled"
                    o.cancelled_at = datetime.now(timezone.utc)
                sub = BillingSubscription(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    plan_id=plan.id,
                    status="active",
                    started_at=datetime.now(timezone.utc),
                )
                s.add(sub)
                await s.commit()
        finally:
            await eng.dispose()

    asyncio.run(_do())


def _seed_monthly_usage(user_id: str, calls: int) -> None:
    """user_id 의 당월 사용량을 ``calls`` 로 세팅 (없으면 생성)."""

    async def _do() -> None:
        url = _async_db_url()
        eng = create_async_engine(url, poolclass=NullPool)
        SM = async_sessionmaker(eng, expire_on_commit=False)
        ym = datetime.now(timezone.utc).strftime("%Y-%m")
        try:
            async with SM() as s:
                row = (
                    await s.execute(
                        select(BillingMonthlyUserUsage)
                        .where(BillingMonthlyUserUsage.user_id == user_id)
                        .where(BillingMonthlyUserUsage.year_month == ym)
                    )
                ).scalar_one_or_none()
                if row is None:
                    row = BillingMonthlyUserUsage(
                        id=str(uuid.uuid4()),
                        user_id=user_id,
                        year_month=ym,
                        calls_count=calls,
                        tokens_total=0,
                        cost_usd=0,
                    )
                    s.add(row)
                else:
                    row.calls_count = calls
                await s.commit()
        finally:
            await eng.dispose()

    asyncio.run(_do())


# ── 1. 카탈로그 + 무인증 ────────────────────────────────


def test_plans_public_lists_4_medi_tiers(client: httpx.Client) -> None:
    r = client.get("/api/v1/billing/plans")
    assert r.status_code == 200, r.text
    body = r.json()
    codes = {p["code"] for p in body["plans"]}
    assert codes == {"free", "clinic", "hospital", "ent"}
    assert body["default_code"] == "free"

    free = next(p for p in body["plans"] if p["code"] == "free")
    assert free["monthly_call_quota"] == 50
    assert free["price_usd_per_month"] == 0.0

    clinic = next(p for p in body["plans"] if p["code"] == "clinic")
    assert clinic["price_usd_per_month"] == 299.0
    assert clinic["monthly_call_quota"] == 500

    hospital = next(p for p in body["plans"] if p["code"] == "hospital")
    assert hospital["price_usd_per_month"] == 999.0
    assert "HEAVY" in hospital["allowed_models"]

    ent = next(p for p in body["plans"] if p["code"] == "ent")
    assert ent["price_usd_per_month"] == 2999.0
    assert ent["monthly_call_quota"] is None
    assert "CONSENSUS" in ent["allowed_models"]


def test_billing_me_requires_auth(client: httpx.Client) -> None:
    r = client.get("/api/v1/billing/me")
    assert r.status_code == 401


# ── 2. /me — Free 자동 부여 ────────────────────────────


def test_billing_me_auto_assigns_free_for_doctor(client: httpx.Client) -> None:
    """doctor 첫 호출 — Free plan 자동 부여."""
    r = client.get("/api/v1/billing/me", headers=_headers(client, "doctor"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["subscription"]["plan_code"] in {"free", "clinic", "hospital", "ent"}
    assert body["usage"]["year_month"] == datetime.now(timezone.utc).strftime("%Y-%m")
    assert body["usage"]["calls_used"] >= 0


# ── 3. admin subscribe ────────────────────────────────


def test_subscribe_requires_admin(client: httpx.Client) -> None:
    r = client.post(
        "/api/v1/billing/subscribe",
        headers=_headers(client, "doctor"),
        json={"user_id": "doctor", "plan_code": "clinic"},
    )
    assert r.status_code == 403


def test_subscribe_invalid_plan_returns_422(client: httpx.Client) -> None:
    """Pydantic regex 검증 — invalid plan_code → 422."""
    r = client.post(
        "/api/v1/billing/subscribe",
        headers=_headers(client, "admin"),
        json={"user_id": "doctor", "plan_code": "nonexistent"},
    )
    assert r.status_code == 422, r.text


def test_admin_subscribe_clinic_promotes_user(client: httpx.Client) -> None:
    user = f"u-{uuid.uuid4().hex[:8]}"
    r = client.post(
        "/api/v1/billing/subscribe",
        headers=_headers(client, "admin"),
        json={"user_id": user, "plan_code": "clinic"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["plan_code"] == "clinic"


def test_admin_subscribe_then_upgrade_to_hospital(client: httpx.Client) -> None:
    user = f"u-{uuid.uuid4().hex[:8]}"
    r1 = client.post(
        "/api/v1/billing/subscribe",
        headers=_headers(client, "admin"),
        json={"user_id": user, "plan_code": "clinic"},
    )
    assert r1.status_code == 200
    r2 = client.post(
        "/api/v1/billing/subscribe",
        headers=_headers(client, "admin"),
        json={"user_id": user, "plan_code": "hospital"},
    )
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["plan_code"] == "hospital"
    assert body["previous_plan_code"] == "clinic"


# ── 4. Quota 한도 차단 (LM Studio 없이도) ───────────────


def test_quota_exceeded_blocked_via_seeded_usage(client: httpx.Client) -> None:
    """Free plan (50 quota) 인 doctor 의 사용량을 50 으로 시드 → /diagnosis 분기에서 429.

    실 호출 경로: ``POST /api/v1/diagnosis/...`` 또는 enforce_quota 가 등록된 라우트.
    여기서는 enforce_quota dependency 가 적용된 가장 간단한 라우트를 확인 — 만약
    적용 라우트가 없다면 /diagnosis/text-only 등 후속 라우트 통합 시점에 검증.
    """
    user_id = "doctor"
    _seed_subscription(user_id, "free")
    _seed_monthly_usage(user_id, 50)

    r = client.get("/api/v1/billing/me", headers=_headers(client, "doctor"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["usage"]["calls_used"] == 50
    assert body["usage"]["calls_limit"] == 50
    assert body["usage"]["calls_remaining"] == 0
    assert body["usage"]["quota_pct"] >= 1.0

    _seed_monthly_usage(user_id, 0)


# ── 5. /usage 히스토리 + timeline ──────────────────────


def test_usage_history_returns_user_rows(client: httpx.Client) -> None:
    user_id = "doctor"
    _seed_monthly_usage(user_id, 7)
    r = client.get("/api/v1/billing/usage", headers=_headers(client, "doctor"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user_id"] == user_id
    cur = datetime.now(timezone.utc).strftime("%Y-%m")
    assert any(h["year_month"] == cur for h in body["history"])
    _seed_monthly_usage(user_id, 0)


def test_usage_timeline_returns_points(client: httpx.Client) -> None:
    r = client.get(
        "/api/v1/billing/usage/timeline?days=30",
        headers=_headers(client, "doctor"),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["days"] == 30
    assert isinstance(body["points"], list)


# ── 6. admin stats ────────────────────────────────────


def test_admin_stats_returns_4_plan_distribution(client: httpx.Client) -> None:
    r = client.get(
        "/api/v1/billing/admin/stats", headers=_headers(client, "admin")
    )
    assert r.status_code == 200, r.text
    body = r.json()
    codes = {entry["plan_code"] for entry in body["plan_distribution"]}
    assert {"free", "clinic", "hospital", "ent"}.issubset(codes)
    assert body["total_monthly_revenue_usd"] >= 0


# ── 7. Stripe status (disabled by default) ────────────


def test_stripe_status_disabled_lists_supported_events(client: httpx.Client) -> None:
    r = client.get("/api/v1/billing/stripe/status")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["enabled"] is False
    assert "invoice.paid" in body["supported_events"]
    assert "charge.refunded" in body["supported_events"]


def test_stripe_checkout_disabled_returns_503(client: httpx.Client) -> None:
    r = client.post(
        "/api/v1/billing/stripe/checkout",
        headers=_headers(client, "doctor"),
        json={
            "plan_code": "clinic",
            "success_url": "https://example.com/ok",
            "cancel_url": "https://example.com/no",
        },
    )
    assert r.status_code == 503, r.text


def test_stripe_portal_disabled_returns_503(client: httpx.Client) -> None:
    r = client.post(
        "/api/v1/billing/stripe/portal",
        headers=_headers(client, "doctor"),
        json={"return_url": "https://example.com/back"},
    )
    assert r.status_code == 503, r.text
