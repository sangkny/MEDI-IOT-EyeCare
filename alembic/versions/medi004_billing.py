"""medi004 — MEDI SaaS billing (Phase 2 D Round 2 Day 1, 2026-05-13).

ADK adk006 / CoOps cop003 와 동일 schema, **prefix=``medi_``** + Stripe sidecar.
4 tier plans 시드:
    - free       — 월  50회, FAST          (개인 의사 체험)
    - clinic     — 월 500회, FAST          ($299, 1인 의원)
    - hospital   — 월 5,000회, FAST+HEAVY   ($999, 중소 병원)
    - ent        — 무제한, FAST+HEAVY+CONSENSUS ($2,999, 대형 병원·SLA)

표 한 장 — 본 가격은 ``SaaS-플랫폼-한장요약.md`` 의 MEDI Year 1-3 매출 계획과 정합.
"""
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "medi004_billing"
down_revision: Union[str, None] = "medi003_clinical_studies"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── billing 4 테이블 ─────────────────────────────────────
    op.create_table(
        "medi_billing_plans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column(
            "price_usd_per_month", sa.Numeric(10, 2),
            nullable=False, server_default="0",
        ),
        sa.Column("monthly_call_quota", sa.Integer(), nullable=True),
        sa.Column(
            "allowed_models", sa.String(length=128),
            nullable=False, server_default="FAST",
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_medi_billing_plans_code"),
    )
    op.create_index(
        "ix_medi_billing_plans_code", "medi_billing_plans", ["code"], unique=True
    )

    op.create_table(
        "medi_billing_subscriptions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column(
            "started_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["medi_billing_plans.id"], ondelete="RESTRICT"
        ),
    )
    op.create_index(
        "ix_medi_billing_subscriptions_user_id", "medi_billing_subscriptions", ["user_id"]
    )
    op.create_index(
        "ix_medi_billing_subscriptions_status", "medi_billing_subscriptions", ["status"]
    )

    op.create_table(
        "medi_billing_usage_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("plan_code", sa.String(length=32), nullable=False),
        sa.Column("tokens_estimated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("model_used", sa.String(length=128), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_medi_billing_usage_records_user_id",
        "medi_billing_usage_records", ["user_id"],
    )
    op.create_index(
        "ix_medi_billing_usage_records_action",
        "medi_billing_usage_records", ["action"],
    )
    op.create_index(
        "ix_medi_billing_usage_records_created_at",
        "medi_billing_usage_records", ["created_at"],
    )

    op.create_table(
        "medi_billing_monthly_user_usage",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("year_month", sa.String(length=7), nullable=False),
        sa.Column("calls_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(18, 8), nullable=False, server_default="0"),
        sa.Column(
            "last_updated", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "year_month", name="uq_medi_billing_monthly_user_year_month"
        ),
    )
    op.create_index(
        "ix_medi_billing_monthly_user_usage_user_id",
        "medi_billing_monthly_user_usage", ["user_id"],
    )
    op.create_index(
        "ix_medi_billing_monthly_user_usage_year_month",
        "medi_billing_monthly_user_usage", ["year_month"],
    )

    # ── Stripe sidecar (B-7 패턴) ─────────────────────────────
    op.create_table(
        "medi_stripe_plan_mappings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("stripe_price_id", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["medi_billing_plans.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", name="uq_medi_stripe_plan_mappings_plan_id"),
        sa.UniqueConstraint(
            "stripe_price_id",
            name="uq_medi_stripe_plan_mappings_stripe_price_id",
        ),
    )
    op.create_index(
        "ix_medi_stripe_plan_mappings_plan_id",
        "medi_stripe_plan_mappings", ["plan_id"],
    )
    op.create_index(
        "ix_medi_stripe_plan_mappings_stripe_price_id",
        "medi_stripe_plan_mappings", ["stripe_price_id"],
    )

    op.create_table(
        "medi_stripe_subscriptions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("subscription_id", sa.String(length=36), nullable=False),
        sa.Column("stripe_customer_id", sa.String(length=128), nullable=False),
        sa.Column("stripe_subscription_id", sa.String(length=128), nullable=False),
        sa.Column(
            "stripe_status", sa.String(length=32),
            nullable=False, server_default="incomplete",
        ),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "cancel_at_period_end", sa.Boolean(),
            nullable=False, server_default=sa.text("false"),
        ),
        # R2 컬럼 3 (invoice/refund) 처음부터 포함
        sa.Column("last_paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_paid_amount_cents", sa.BigInteger(), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"], ["medi_billing_subscriptions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "subscription_id", name="uq_medi_stripe_subscriptions_subscription_id"
        ),
        sa.UniqueConstraint(
            "stripe_subscription_id",
            name="uq_medi_stripe_subscriptions_stripe_subscription_id",
        ),
    )
    op.create_index(
        "ix_medi_stripe_subscriptions_subscription_id",
        "medi_stripe_subscriptions", ["subscription_id"],
    )
    op.create_index(
        "ix_medi_stripe_subscriptions_stripe_customer_id",
        "medi_stripe_subscriptions", ["stripe_customer_id"],
    )
    op.create_index(
        "ix_medi_stripe_subscriptions_stripe_subscription_id",
        "medi_stripe_subscriptions", ["stripe_subscription_id"],
    )

    # ── 4 plan 시드 (의료 SaaS — 한장요약 §MEDI Year 1-3 매출) ─
    bind = op.get_bind()
    now = datetime.now(timezone.utc)
    seed_plans = [
        {
            "id": "medi-plan-free",
            "code": "free",
            "name": "Free",
            "price": 0,
            "quota": 50,
            "models": "FAST",
            "desc": "개인 의사 체험 — 월 50회 분석, FAST 모델 (LOCAL_FAST)",
        },
        {
            "id": "medi-plan-clinic",
            "code": "clinic",
            "name": "Clinic",
            "price": 299,
            "quota": 500,
            "models": "FAST",
            "desc": "1인 의원 — 월 500회, FAST 모델, 의사 1인 라이선스",
        },
        {
            "id": "medi-plan-hospital",
            "code": "hospital",
            "name": "Hospital",
            "price": 999,
            "quota": 5000,
            "models": "FAST,HEAVY",
            "desc": "중소 병원 — 월 5,000회, FAST+HEAVY 모델, 의사 5인까지",
        },
        {
            "id": "medi-plan-ent",
            "code": "ent",
            "name": "Enterprise",
            "price": 2999,
            "quota": None,
            "models": "FAST,HEAVY,CONSENSUS",
            "desc": "대형 병원 — 무제한, 전체 모델 + CONSENSUS, SLA 99.95% + 임상연구 전용 큐",
        },
    ]
    for p in seed_plans:
        bind.execute(
            sa.text(
                "INSERT INTO medi_billing_plans "
                "(id, code, name, price_usd_per_month, monthly_call_quota, "
                " allowed_models, description, is_active, created_at, updated_at) "
                "VALUES (:id, :code, :name, :price, :quota, :models, :desc, "
                "        true, :now, :now)"
            ),
            {
                "id": p["id"],
                "code": p["code"],
                "name": p["name"],
                "price": p["price"],
                "quota": p["quota"],
                "models": p["models"],
                "desc": p["desc"],
                "now": now,
            },
        )


def downgrade() -> None:
    op.drop_index(
        "ix_medi_stripe_subscriptions_stripe_subscription_id",
        table_name="medi_stripe_subscriptions",
    )
    op.drop_index(
        "ix_medi_stripe_subscriptions_stripe_customer_id",
        table_name="medi_stripe_subscriptions",
    )
    op.drop_index(
        "ix_medi_stripe_subscriptions_subscription_id",
        table_name="medi_stripe_subscriptions",
    )
    op.drop_table("medi_stripe_subscriptions")

    op.drop_index(
        "ix_medi_stripe_plan_mappings_stripe_price_id",
        table_name="medi_stripe_plan_mappings",
    )
    op.drop_index(
        "ix_medi_stripe_plan_mappings_plan_id",
        table_name="medi_stripe_plan_mappings",
    )
    op.drop_table("medi_stripe_plan_mappings")

    op.drop_index(
        "ix_medi_billing_monthly_user_usage_year_month",
        table_name="medi_billing_monthly_user_usage",
    )
    op.drop_index(
        "ix_medi_billing_monthly_user_usage_user_id",
        table_name="medi_billing_monthly_user_usage",
    )
    op.drop_table("medi_billing_monthly_user_usage")

    op.drop_index(
        "ix_medi_billing_usage_records_created_at",
        table_name="medi_billing_usage_records",
    )
    op.drop_index(
        "ix_medi_billing_usage_records_action",
        table_name="medi_billing_usage_records",
    )
    op.drop_index(
        "ix_medi_billing_usage_records_user_id",
        table_name="medi_billing_usage_records",
    )
    op.drop_table("medi_billing_usage_records")

    op.drop_index(
        "ix_medi_billing_subscriptions_status",
        table_name="medi_billing_subscriptions",
    )
    op.drop_index(
        "ix_medi_billing_subscriptions_user_id",
        table_name="medi_billing_subscriptions",
    )
    op.drop_table("medi_billing_subscriptions")

    op.drop_index("ix_medi_billing_plans_code", table_name="medi_billing_plans")
    op.drop_table("medi_billing_plans")
