"""medi010 — 외부 임상 데이터 가져오기 스테이징.

이 식별자는 Alembic 개정 이름이다. 개발 단계 번호가 아니다.
medi003부터 medi009까지는 수정하지 않는다.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "medi010_external_clinical_import"
down_revision: Union[str, None] = "medi009_clinical_data_lock"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "import_sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("source_system", sa.String(length=64), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["study_id"], ["clinical_studies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("study_id", "content_sha256", name="uq_import_sources_sha"),
    )
    op.create_index("ix_import_sources_study_id", "import_sources", ["study_id"])
    op.create_table(
        "import_batches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("site_id", sa.String(length=36), nullable=False),
        sa.Column("mapping_version", sa.String(length=64), nullable=False),
        sa.Column("adapter", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("actor_user_id", sa.String(length=64), nullable=False),
        sa.Column("summary_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["study_sites.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_id"], ["import_sources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["study_id"], ["clinical_studies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_batches_source_id", "import_batches", ["source_id"])
    op.create_index("ix_import_batches_study_id", "import_batches", ["study_id"])
    op.create_table(
        "import_staging_rows",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("batch_id", sa.String(length=36), nullable=False),
        sa.Column("sheet_name", sa.String(length=200), nullable=False),
        sa.Column("sheet_index", sa.Integer(), nullable=False),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("subject_code", sa.String(length=64), nullable=True),
        sa.Column("visit_code", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("sensitive_hashes_json", sa.Text(), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["batch_id"], ["import_batches.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_staging_rows_batch_id", "import_staging_rows", ["batch_id"])
    op.create_table(
        "import_links",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("natural_key", sa.String(length=200), nullable=False),
        sa.Column("value_sha256", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("batch_id", sa.String(length=36), nullable=False),
        sa.Column("item_id", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["import_batches.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["study_id"], ["clinical_studies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("study_id", "natural_key", name="uq_import_links_natural"),
    )
    op.create_index("ix_import_links_study_id", "import_links", ["study_id"])
    op.create_table(
        "import_discrepancies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("link_id", sa.String(length=36), nullable=False),
        sa.Column("batch_id", sa.String(length=36), nullable=False),
        sa.Column("previous_sha256", sa.String(length=64), nullable=False),
        sa.Column("new_sha256", sa.String(length=64), nullable=False),
        sa.Column("new_value_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["import_batches.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["link_id"], ["import_links.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["study_id"], ["clinical_studies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_discrepancies_study_id", "import_discrepancies", ["study_id"])
    op.create_index("ix_import_discrepancies_link_id", "import_discrepancies", ["link_id"])
    op.create_table(
        "import_validation_findings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("batch_id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("subject_code", sa.String(length=64), nullable=True),
        sa.Column("visit_code", sa.String(length=64), nullable=True),
        sa.Column("item_id", sa.String(length=64), nullable=True),
        sa.Column("classification", sa.String(length=32), nullable=False),
        sa.Column("rule_code", sa.String(length=64), nullable=False),
        sa.Column("message_code", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["import_batches.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["study_id"], ["clinical_studies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_validation_findings_batch_id", "import_validation_findings", ["batch_id"])
    op.create_index("ix_import_validation_findings_study_id", "import_validation_findings", ["study_id"])


def downgrade() -> None:
    op.drop_table("import_validation_findings")
    op.drop_table("import_discrepancies")
    op.drop_table("import_links")
    op.drop_table("import_staging_rows")
    op.drop_table("import_batches")
    op.drop_table("import_sources")
