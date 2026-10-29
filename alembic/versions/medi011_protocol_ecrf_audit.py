"""medi011 — 계획서 버전, eCRF 스키마, 감사 체인.

이 식별자는 Alembic 개정 이름이다. 개발 단계 번호가 아니다.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "medi011_protocol_ecrf_audit"
down_revision: Union[str, None] = "medi010_external_clinical_import"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "protocol_documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("protocol_identifier", sa.String(length=64), nullable=False),
        sa.Column("version_label", sa.String(length=16), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("document_date", sa.String(length=16), nullable=False),
        sa.Column("source_reference", sa.String(length=200), nullable=False),
        sa.Column("source_present", sa.Boolean(), nullable=False),
        sa.Column("extraction_status", sa.String(length=32), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("approval_status", sa.String(length=32), nullable=False),
        sa.Column("activation_status", sa.String(length=16), nullable=False),
        sa.Column("simulated_approval", sa.Boolean(), nullable=False),
        sa.Column("parent_document_id", sa.String(length=36), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("effective_date", sa.String(length=16), nullable=True),
        sa.ForeignKeyConstraint(["study_id"], ["clinical_studies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("study_id", "protocol_identifier", "version_label", name="uq_protocol_documents_version"),
    )
    op.create_index("ix_protocol_documents_study", "protocol_documents", ["study_id"])
    op.create_table(
        "ecrf_schema_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("schema_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("definition_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["protocol_documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["study_id"], ["clinical_studies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ecrf_schema_versions_document", "ecrf_schema_versions", ["document_id"])
    op.create_index("ix_ecrf_schema_versions_study", "ecrf_schema_versions", ["study_id"])
    op.create_table(
        "ecrf_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("site_id", sa.String(length=36), nullable=False),
        sa.Column("subject_id", sa.String(length=36), nullable=False),
        sa.Column("visit_id", sa.String(length=36), nullable=False),
        sa.Column("schema_version_id", sa.String(length=36), nullable=False),
        sa.Column("protocol_version", sa.String(length=16), nullable=False),
        sa.Column("logical_field_id", sa.String(length=64), nullable=False),
        sa.Column("repeat_index", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("value_number", sa.Numeric(12, 4), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("record_status", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "visit_id", "schema_version_id", "logical_field_id", "repeat_index", "revision",
            name="uq_ecrf_entries_revision",
        ),
    )
    op.create_index("ix_ecrf_entries_visit", "ecrf_entries", ["visit_id"])
    op.create_index("ix_ecrf_entries_schema", "ecrf_entries", ["schema_version_id"])
    op.create_table(
        "audit_event_chains",
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("chain_seq", sa.Integer(), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("actor_role", sa.String(length=32), nullable=True),
        sa.Column("protocol_version", sa.String(length=16), nullable=True),
        sa.Column("schema_version_id", sa.String(length=36), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
        sa.UniqueConstraint("study_id", "chain_seq", name="uq_audit_event_chains_seq"),
    )
    op.create_index("ix_audit_event_chains_study", "audit_event_chains", ["study_id"])
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE TRIGGER audit_event_chains_append_only
            BEFORE UPDATE OR DELETE ON audit_event_chains
            FOR EACH ROW EXECUTE FUNCTION reject_append_only_clinical_history()
            """
        )
    elif bind.dialect.name == "sqlite":
        op.execute(
            """
            CREATE TRIGGER audit_event_chains_append_only_update
            BEFORE UPDATE ON audit_event_chains
            BEGIN
              SELECT RAISE(ABORT, 'append-only clinical history');
            END
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS audit_event_chains_append_only ON audit_event_chains")
    elif bind.dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS audit_event_chains_append_only_update")
    op.drop_table("audit_event_chains")
    op.drop_table("ecrf_entries")
    op.drop_table("ecrf_schema_versions")
    op.drop_table("protocol_documents")
