"""medi008 — 임상 질의와 품질 실행 기록.

운영 데이터베이스에는 적용하지 않는다. upgrade 는 추가만 한다.
medi006 과 medi007 은 고치지 않는다.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "medi008_clinical_query"
down_revision: Union[str, None] = "medi007_ecrf_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("data_quality_findings", sa.Column("source_revision", sa.Integer(), nullable=True))
    op.add_column(
        "data_quality_findings",
        sa.Column("evaluation_scope", sa.String(length=16), nullable=False, server_default="study"),
    )
    op.add_column(
        "data_quality_findings",
        sa.Column("evaluation_scope_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "data_quality_findings",
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "quality_evaluation_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("scope_id", sa.String(length=36), nullable=True),
        sa.Column("trigger", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("actor_user_id", sa.String(length=64), nullable=False),
        sa.Column("finding_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["study_id"], ["clinical_studies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quality_evaluation_runs_study_id", "quality_evaluation_runs", ["study_id"])
    op.create_table(
        "clinical_queries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("site_id", sa.String(length=36), nullable=True),
        sa.Column("subject_id", sa.String(length=36), nullable=True),
        sa.Column("visit_id", sa.String(length=36), nullable=True),
        sa.Column("definition_id", sa.String(length=36), nullable=True),
        sa.Column("observation_id", sa.String(length=36), nullable=True),
        sa.Column("finding_id", sa.String(length=36), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("assigned_user_id", sa.String(length=64), nullable=True),
        sa.Column("assigned_role", sa.String(length=32), nullable=True),
        sa.Column("opened_by", sa.String(length=64), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["definition_id"], ["questionnaire_definitions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["finding_id"], ["data_quality_findings.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["observation_id"], ["clinical_observations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["site_id"], ["study_sites.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["study_id"], ["clinical_studies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subject_id"], ["study_subjects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["visit_id"], ["study_visits.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clinical_queries_study_status", "clinical_queries", ["study_id", "status"])
    op.create_table(
        "clinical_query_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("query_id", sa.String(length=36), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=True),
        sa.Column("to_status", sa.String(length=20), nullable=False),
        sa.Column("actor_user_id", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("detail_json", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["query_id"], ["clinical_queries.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clinical_query_events_query_id", "clinical_query_events", ["query_id"])
    op.create_table(
        "clinical_query_responses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("query_id", sa.String(length=36), nullable=False),
        sa.Column("author_user_id", sa.String(length=64), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["query_id"], ["clinical_queries.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clinical_query_responses_query_id", "clinical_query_responses", ["query_id"])


def downgrade() -> None:
    op.drop_index("ix_clinical_query_responses_query_id", table_name="clinical_query_responses")
    op.drop_table("clinical_query_responses")
    op.drop_index("ix_clinical_query_events_query_id", table_name="clinical_query_events")
    op.drop_table("clinical_query_events")
    op.drop_index("ix_clinical_queries_study_status", table_name="clinical_queries")
    op.drop_table("clinical_queries")
    op.drop_index("ix_quality_evaluation_runs_study_id", table_name="quality_evaluation_runs")
    op.drop_table("quality_evaluation_runs")
    op.drop_column("data_quality_findings", "evaluated_at")
    op.drop_column("data_quality_findings", "evaluation_scope_id")
    op.drop_column("data_quality_findings", "evaluation_scope")
    op.drop_column("data_quality_findings", "source_revision")
