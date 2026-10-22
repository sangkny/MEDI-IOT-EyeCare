"""medi007 — eCRF 기초 열과 Visit-폼 배정.

운영 데이터베이스에는 적용하지 않는다. upgrade 는 추가만 한다.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "medi007_ecrf_foundation"
down_revision: Union[str, None] = "medi006_clinical_support"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("questionnaire_responses", sa.Column("correction_reason", sa.Text(), nullable=True))
    op.add_column("questionnaire_responses", sa.Column("finalized_by", sa.String(length=64), nullable=True))
    op.add_column(
        "questionnaire_responses",
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "visit_form_assignments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("visit_code", sa.String(length=64), nullable=False),
        sa.Column("definition_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["definition_id"], ["questionnaire_definitions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["study_id"], ["clinical_studies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "study_id", "visit_code", "definition_id", name="uq_visit_form_assignment",
        ),
    )


def downgrade() -> None:
    op.drop_table("visit_form_assignments")
    op.drop_column("questionnaire_responses", "finalized_at")
    op.drop_column("questionnaire_responses", "finalized_by")
    op.drop_column("questionnaire_responses", "correction_reason")
