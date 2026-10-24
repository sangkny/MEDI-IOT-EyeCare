"""medi009 — 임상 데이터 잠금, 준비도, 모니터링 지표.

운영 데이터베이스에는 적용하지 않는다. 기존 마이그레이션은 고치지 않는다.
감사 이벤트와 잠금 이력은 추가만 허용한다.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "medi009_clinical_data_lock"
down_revision: Union[str, None] = "medi008_clinical_query"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("clinical_audit_events", sa.Column("previous_state", sa.String(length=32), nullable=True))
    op.add_column("clinical_audit_events", sa.Column("new_state", sa.String(length=32), nullable=True))
    op.add_column("clinical_audit_events", sa.Column("reason", sa.Text(), nullable=True))
    op.add_column("clinical_audit_events", sa.Column("target_revision", sa.Integer(), nullable=True))
    op.add_column("clinical_audit_events", sa.Column("payload_json", sa.Text(), nullable=True))
    op.add_column("data_lock_records", sa.Column("site_id", sa.String(length=36), nullable=True))
    op.add_column("data_lock_records", sa.Column("lock_state_id", sa.String(length=36), nullable=True))
    op.add_column("data_lock_records", sa.Column("from_state", sa.String(length=32), nullable=True))
    op.add_column("data_lock_records", sa.Column("to_state", sa.String(length=32), nullable=True))
    op.add_column("data_lock_records", sa.Column("state_version", sa.Integer(), nullable=True))
    op.add_column("data_lock_records", sa.Column("request_id", sa.String(length=64), nullable=True))
    op.add_column("data_lock_records", sa.Column("target_revision", sa.Integer(), nullable=True))
    op.add_column("data_lock_records", sa.Column("unlock_request_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_data_lock_records_site_id", "data_lock_records", "study_sites", ["site_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_table(
        "data_lock_states",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("site_id", sa.String(length=36), nullable=True),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("target_revision", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["study_sites.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["study_id"], ["clinical_studies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("study_id", "target_type", "target_id", name="uq_data_lock_states_target"),
    )
    op.create_index("ix_data_lock_states_study_id", "data_lock_states", ["study_id"])
    op.create_table(
        "data_unlock_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("lock_state_id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("site_id", sa.String(length=36), nullable=True),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("lock_state_at_request", sa.String(length=32), nullable=False),
        sa.Column("requesting_user_id", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("decided_by", sa.String(length=64), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["lock_state_id"], ["data_lock_states.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["site_id"], ["study_sites.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["study_id"], ["clinical_studies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_unlock_requests_lock_state_id", "data_unlock_requests", ["lock_state_id"])
    op.create_unique_constraint(
        "uq_data_lock_records_version", "data_lock_records", ["lock_state_id", "state_version"],
    )
    op.create_table(
        "study_protocol_definitions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requirements_json", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("approved_by", sa.String(length=64), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["study_id"], ["clinical_studies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("study_id", "version_number", name="uq_study_protocol_definitions_version"),
    )
    op.create_index("ix_study_protocol_definitions_study_id", "study_protocol_definitions", ["study_id"])
    op.create_table(
        "monitoring_indicator_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("protocol_definition_id", sa.String(length=36), nullable=True),
        sa.Column("actor_user_id", sa.String(length=64), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["protocol_definition_id"], ["study_protocol_definitions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["study_id"], ["clinical_studies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_monitoring_indicator_runs_study_id", "monitoring_indicator_runs", ["study_id"])
    op.create_table(
        "monitoring_indicators",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("site_id", sa.String(length=36), nullable=True),
        sa.Column("subject_id", sa.String(length=36), nullable=True),
        sa.Column("visit_id", sa.String(length=36), nullable=True),
        sa.Column("indicator_code", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["monitoring_indicator_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["site_id"], ["study_sites.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["study_id"], ["clinical_studies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subject_id"], ["study_subjects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["visit_id"], ["study_visits.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_monitoring_indicators_run_id", "monitoring_indicators", ["run_id"])
    op.create_index("ix_monitoring_indicators_study_id", "monitoring_indicators", ["study_id"])
    _append_only_triggers()


def _append_only_triggers() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION reject_append_only_clinical_history()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
              RAISE EXCEPTION 'append-only clinical history';
            END;
            $$
            """
        )
        op.execute(
            """
            CREATE TRIGGER clinical_audit_events_append_only
            BEFORE UPDATE OR DELETE ON clinical_audit_events
            FOR EACH ROW EXECUTE FUNCTION reject_append_only_clinical_history()
            """
        )
        op.execute(
            """
            CREATE TRIGGER data_lock_records_append_only
            BEFORE UPDATE OR DELETE ON data_lock_records
            FOR EACH ROW EXECUTE FUNCTION reject_append_only_clinical_history()
            """
        )
        return
    if bind.dialect.name != "sqlite":
        return
    for table in ("clinical_audit_events", "data_lock_records"):
        op.execute(
            f"""
            CREATE TRIGGER {table}_append_only_update
            BEFORE UPDATE ON {table}
            BEGIN
              SELECT RAISE(ABORT, 'append-only clinical history');
            END
            """
        )
        op.execute(
            f"""
            CREATE TRIGGER {table}_append_only_delete
            BEFORE DELETE ON {table}
            BEGIN
              SELECT RAISE(ABORT, 'append-only clinical history');
            END
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS data_lock_records_append_only ON data_lock_records")
        op.execute("DROP TRIGGER IF EXISTS clinical_audit_events_append_only ON clinical_audit_events")
        op.execute("DROP FUNCTION IF EXISTS reject_append_only_clinical_history()")
    elif bind.dialect.name == "sqlite":
        for name in (
            "data_lock_records_append_only_delete",
            "data_lock_records_append_only_update",
            "clinical_audit_events_append_only_delete",
            "clinical_audit_events_append_only_update",
        ):
            op.execute(f"DROP TRIGGER IF EXISTS {name}")
    op.drop_index("ix_monitoring_indicators_study_id", table_name="monitoring_indicators")
    op.drop_index("ix_monitoring_indicators_run_id", table_name="monitoring_indicators")
    op.drop_table("monitoring_indicators")
    op.drop_index("ix_monitoring_indicator_runs_study_id", table_name="monitoring_indicator_runs")
    op.drop_table("monitoring_indicator_runs")
    op.drop_index("ix_study_protocol_definitions_study_id", table_name="study_protocol_definitions")
    op.drop_table("study_protocol_definitions")
    op.drop_constraint("uq_data_lock_records_version", "data_lock_records", type_="unique")
    op.drop_index("ix_data_unlock_requests_lock_state_id", table_name="data_unlock_requests")
    op.drop_table("data_unlock_requests")
    op.drop_index("ix_data_lock_states_study_id", table_name="data_lock_states")
    op.drop_table("data_lock_states")
    op.drop_constraint("fk_data_lock_records_site_id", "data_lock_records", type_="foreignkey")
    for column in (
        "unlock_request_id",
        "target_revision",
        "request_id",
        "state_version",
        "to_state",
        "from_state",
        "lock_state_id",
        "site_id",
    ):
        op.drop_column("data_lock_records", column)
    for column in ("payload_json", "target_revision", "reason", "new_state", "previous_state"):
        op.drop_column("clinical_audit_events", column)
