#!/usr/bin/env python3
"""
파일명: seed_stripe_plan_mappings.py
목적: seed_stripe_plan_mappings.py 실행 스크립트
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가

MEDI Stripe plan ↔ Price 매핑 시드 (idempotent).

``medi004_billing`` 이 만든 ``medi_billing_plans`` (id: medi-plan-*) 와
``medi_stripe_plan_mappings`` 를 env 의 Stripe Price ID 로 연결한다.

환경 변수 (비어 있으면 해당 plan 은 건너뜀):

  MEDI_STRIPE_PRICE_ID_FREE
  MEDI_STRIPE_PRICE_ID_CLINIC   (별칭 MEDI_STRIPE_PRICE_ID_BASIC)
  MEDI_STRIPE_PRICE_ID_HOSPITAL (별칭 MEDI_STRIPE_PRICE_ID_PRO)
  MEDI_STRIPE_PRICE_ID_ENT

사용:

  cd projects/MEDI-IOT-EyeCare
  export MEDI_STRIPE_PRICE_ID_CLINIC=price_...
  python scripts/seed_stripe_plan_mappings.py

  # Docker
  docker compose -f ../docker-compose.dev.yml exec medi-iot-api \\
    python scripts/seed_stripe_plan_mappings.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid

from sqlalchemy import select

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import async_session_maker
from models.billing import BillingPlan, StripePlanMapping


def _price(env_keys: tuple[str, ...]) -> str:
    for key in env_keys:
        val = (os.environ.get(key) or "").strip()
        if val:
            return val
    return ""


PLAN_ENV: list[tuple[str, tuple[str, ...]]] = [
    ("medi-plan-free", ("MEDI_STRIPE_PRICE_ID_FREE",)),
    (
        "medi-plan-clinic",
        ("MEDI_STRIPE_PRICE_ID_CLINIC", "MEDI_STRIPE_PRICE_ID_BASIC"),
    ),
    (
        "medi-plan-hospital",
        ("MEDI_STRIPE_PRICE_ID_HOSPITAL", "MEDI_STRIPE_PRICE_ID_PRO"),
    ),
    ("medi-plan-ent", ("MEDI_STRIPE_PRICE_ID_ENT",)),
]


async def seed() -> int:
    upserted = 0
    async with async_session_maker() as session:
        for plan_id, env_keys in PLAN_ENV:
            price_id = _price(env_keys)
            if not price_id:
                print(f"  skip {plan_id} ({env_keys[0]} unset)")
                continue
            plan = await session.scalar(
                select(BillingPlan).where(BillingPlan.id == plan_id)
            )
            if plan is None:
                print(
                    f"  warn {plan_id} not in medi_billing_plans — run alembic upgrade head"
                )
                continue
            row = await session.scalar(
                select(StripePlanMapping).where(
                    StripePlanMapping.plan_id == plan_id
                )
            )
            if row is None:
                session.add(
                    StripePlanMapping(
                        id=str(uuid.uuid4()),
                        plan_id=plan_id,
                        stripe_price_id=price_id,
                    )
                )
                print(f"  insert {plan.code} → {price_id}")
            else:
                row.stripe_price_id = price_id
                print(f"  update {plan.code} → {price_id}")
            upserted += 1
        await session.commit()
    return upserted


def main() -> None:
    print("MEDI stripe_plan_mappings seed")
    n = asyncio.run(seed())
    print(f"done ({n} mapping(s))")


if __name__ == "__main__":
    main()
