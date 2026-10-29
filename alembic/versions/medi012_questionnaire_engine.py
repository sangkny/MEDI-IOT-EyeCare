"""medi012 — 설문 권고 채점과 개선 제안 레지스트리.

이 식별자는 Alembic 개정 이름이다. 개발 단계 번호가 아니다.
기존 questionnaire_* 테이블을 대체하지 않는다.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "medi012_questionnaire_engine"
down_revision: Union[str, None] = "medi011_protocol_ecrf_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "questionnaire_score_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("site_id", sa.String(length=36), nullable=False),
        sa.Column("response_id", sa.String(length=36), nullable=False),
        sa.Column("questionnaire_version_id", sa.String(length=36), nullable=False),
        sa.Column("scoring_version", sa.String(length=32), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("answered_count", sa.Integer(), nullable=False),
        sa.Column("not_applicable_count", sa.Integer(), nullable=False),
        sa.Column("blank_count", sa.Integer(), nullable=False),
        sa.Column("score_sum", sa.Integer(), nullable=True),
        sa.Column("calculated_score", sa.Numeric(12, 4), nullable=True),
        sa.Column("reported_score", sa.Numeric(12, 4), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["response_id"], ["questionnaire_responses.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "response_id", "scoring_version", "revision",
            name="uq_questionnaire_score_results_revision",
        ),
    )
    op.create_index("ix_questionnaire_score_results_study", "questionnaire_score_results", ["study_id"])
    op.create_index("ix_questionnaire_score_results_response", "questionnaire_score_results", ["response_id"])
    op.create_table(
        "improvement_findings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("finding_code", sa.String(length=64), nullable=False),
        sa.Column("source_analyzer", sa.String(length=64), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.Column("module_id", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False),
        sa.Column("proposed_correction", sa.Text(), nullable=False),
        sa.Column("reproduction", sa.Text(), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("fix_ref", sa.String(length=120), nullable=True),
        sa.Column("test_evidence", sa.Text(), nullable=True),
        sa.Column("reanalysis_outcome", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("finding_code"),
    )


def downgrade() -> None:
    op.drop_table("improvement_findings")
    op.drop_table("questionnaire_score_results")
