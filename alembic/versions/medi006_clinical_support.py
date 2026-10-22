"""medi006 — 임상 지원 테이블 초안.

실행하지 않는다. alembic upgrade / downgrade 는 별도 환경 승인 전이다.
upgrade 는 기존 환자·검사·진단 열을 지우거나 의미를 바꾸지 않는다.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "medi006_clinical_support"
down_revision: Union[str, None] = "medi004_billing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "clinical_studies",
        sa.Column(
            "study_kind", sa.String(length=32), nullable=False, server_default="dataset",
        ),
    )
    op.add_column(
        "clinical_studies",
        sa.Column("protocol_version", sa.String(length=64), nullable=True),
    )

    op.create_table(
        "study_sites",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("site_code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["study_id"], ["clinical_studies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("study_id", "site_code", name="uq_study_sites_code"),
    )
    op.create_index("ix_study_sites_study_id", "study_sites", ["study_id"])

    op.create_table(
        "study_site_members",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("site_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["study_sites.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("site_id", "user_id", name="uq_study_site_members_user"),
    )
    op.create_index("ix_study_site_members_site_id", "study_site_members", ["site_id"])

    op.create_table(
        "study_subjects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("site_id", sa.String(length=36), nullable=False),
        sa.Column("subject_code", sa.String(length=64), nullable=False),
        sa.Column("patient_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("enrolled_on", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["site_id"], ["study_sites.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["study_id"], ["clinical_studies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("study_id", "subject_code", name="uq_study_subjects_code"),
    )
    op.create_index("ix_study_subjects_study_id", "study_subjects", ["study_id"])
    op.create_index("ix_study_subjects_site_id", "study_subjects", ["site_id"])

    op.create_table(
        "visit_windows",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("visit_code", sa.String(length=64), nullable=False),
        sa.Column("target_day", sa.Integer(), nullable=False),
        sa.Column("minus_days", sa.Integer(), nullable=False),
        sa.Column("plus_days", sa.Integer(), nullable=False),
        sa.Column("is_baseline", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["study_id"], ["clinical_studies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("study_id", "visit_code", name="uq_visit_windows_code"),
    )
    op.create_index("ix_visit_windows_study_id", "visit_windows", ["study_id"])

    op.create_table(
        "study_visits",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("subject_id", sa.String(length=36), nullable=False),
        sa.Column("visit_code", sa.String(length=64), nullable=False),
        sa.Column("repeat_no", sa.Integer(), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("eye_exam_id", sa.String(length=36), nullable=True),
        sa.Column("diagnosis_id", sa.String(length=36), nullable=True),
        sa.Column("window_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["diagnosis_id"], ["diagnoses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["eye_exam_id"], ["eye_exams.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subject_id"], ["study_subjects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["window_id"], ["visit_windows.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subject_id", "visit_code", "repeat_no", name="uq_study_visits_repeat"),
    )
    op.create_index("ix_study_visits_subject_id", "study_visits", ["subject_id"])

    op.create_table(
        "questionnaire_definitions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["study_id"], ["clinical_studies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("study_id", "code", name="uq_questionnaire_definitions_code"),
    )
    op.create_index("ix_questionnaire_definitions_study_id", "questionnaire_definitions", ["study_id"])

    op.create_table(
        "questionnaire_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("definition_id", sa.String(length=36), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("items_json", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["definition_id"], ["questionnaire_definitions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("definition_id", "version_number", name="uq_questionnaire_versions_number"),
    )
    op.create_index("ix_questionnaire_versions_definition_id", "questionnaire_versions", ["definition_id"])

    op.create_table(
        "questionnaire_responses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("version_id", sa.String(length=36), nullable=False),
        sa.Column("visit_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("recorded_by", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("supersedes_response_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["supersedes_response_id"], ["questionnaire_responses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["version_id"], ["questionnaire_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["visit_id"], ["study_visits.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_questionnaire_responses_version_id", "questionnaire_responses", ["version_id"])
    op.create_index("ix_questionnaire_responses_visit_id", "questionnaire_responses", ["visit_id"])

    op.create_table(
        "questionnaire_response_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("response_id", sa.String(length=36), nullable=False),
        sa.Column("item_code", sa.String(length=64), nullable=False),
        sa.Column("value_json", sa.Text(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["response_id"], ["questionnaire_responses.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("response_id", "item_code", name="uq_questionnaire_response_items_code"),
    )
    op.create_index("ix_questionnaire_response_items_response_id", "questionnaire_response_items", ["response_id"])

    op.create_table(
        "clinical_observations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("visit_id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("laterality", sa.String(length=8), nullable=False),
        sa.Column("method", sa.String(length=32), nullable=False),
        sa.Column("repeat_index", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("value_number", sa.Numeric(12, 4), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(length=16), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("source_observation_id", sa.String(length=36), nullable=True),
        sa.Column("supersedes_observation_id", sa.String(length=36), nullable=True),
        sa.Column("eye_exam_id", sa.String(length=36), nullable=True),
        sa.Column("model_name", sa.String(length=64), nullable=True),
        sa.Column("model_version", sa.String(length=64), nullable=True),
        sa.Column("record_status", sa.String(length=20), nullable=False, server_default="final"),
        sa.Column("correction_reason", sa.Text(), nullable=True),
        sa.Column("finalized_by", sa.String(length=64), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_by", sa.String(length=64), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("row_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["eye_exam_id"], ["eye_exams.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_observation_id"], ["clinical_observations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_observation_id"], ["clinical_observations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["visit_id"], ["study_visits.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "visit_id", "code", "laterality", "method", "repeat_index", "revision",
            name="uq_clinical_observations_revision",
        ),
    )
    op.create_index("ix_clinical_observations_visit_code", "clinical_observations", ["visit_id", "code"])

    op.create_table(
        "data_quality_rules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("logic_json", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["study_id"], ["clinical_studies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("study_id", "code", "version_number", name="uq_data_quality_rules_version"),
    )
    op.create_index("ix_data_quality_rules_study_id", "data_quality_rules", ["study_id"])

    op.create_table(
        "data_quality_findings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("rule_id", sa.String(length=36), nullable=False),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("subject_id", sa.String(length=36), nullable=True),
        sa.Column("visit_id", sa.String(length=36), nullable=True),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("message_code", sa.String(length=64), nullable=False),
        sa.Column("waive_reason", sa.Text(), nullable=True),
        sa.Column("closed_by", sa.String(length=64), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["rule_id"], ["data_quality_rules.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["study_id"], ["clinical_studies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subject_id"], ["study_subjects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["visit_id"], ["study_visits.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_quality_findings_fingerprint", "data_quality_findings", ["fingerprint"])
    op.create_index("ix_data_quality_findings_rule_id", "data_quality_findings", ["rule_id"])
    op.create_index("ix_data_quality_findings_study_id", "data_quality_findings", ["study_id"])

    op.create_table(
        "clinical_audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("site_id", sa.String(length=36), nullable=True),
        sa.Column("actor_user_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["study_sites.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["study_id"], ["clinical_studies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clinical_audit_events_study", "clinical_audit_events", ["study_id", "occurred_at"])

    op.create_table(
        "data_lock_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_user_id", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["study_id"], ["clinical_studies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_lock_records_study_id", "data_lock_records", ["study_id"])

    op.create_table(
        "data_export_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("study_id", sa.String(length=36), nullable=False),
        sa.Column("site_id", sa.String(length=36), nullable=True),
        sa.Column("actor_user_id", sa.String(length=64), nullable=False),
        sa.Column("filter_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("output_sha256", sa.String(length=64), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["site_id"], ["study_sites.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["study_id"], ["clinical_studies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_export_records_study_id", "data_export_records", ["study_id"])


def downgrade() -> None:
    op.drop_table("data_export_records")
    op.drop_table("data_lock_records")
    op.drop_table("clinical_audit_events")
    op.drop_table("data_quality_findings")
    op.drop_table("data_quality_rules")
    op.drop_table("clinical_observations")
    op.drop_table("questionnaire_response_items")
    op.drop_table("questionnaire_responses")
    op.drop_table("questionnaire_versions")
    op.drop_table("questionnaire_definitions")
    op.drop_table("study_visits")
    op.drop_table("visit_windows")
    op.drop_table("study_subjects")
    op.drop_table("study_site_members")
    op.drop_table("study_sites")
    op.drop_column("clinical_studies", "protocol_version")
    op.drop_column("clinical_studies", "study_kind")
