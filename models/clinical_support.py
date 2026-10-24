"""EYECARE 임상 연구 지원 모델.

원본 관찰은 갱신하지 않고 개정 행으로 남긴다. 임상 질의는 별도 이력으로
남기며, 질의 해결이 관찰 값을 바꾸지는 않는다.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base
from models.clinical import ClinicalStudy


def _uuid() -> str:
    return str(uuid.uuid4())


class StudySite(Base):
    __tablename__ = "study_sites"
    __table_args__ = (
        UniqueConstraint("study_id", "site_code", name="uq_study_sites_code"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    study_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clinical_studies.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    site_code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    study: Mapped["ClinicalStudy"] = relationship()
    members: Mapped[list["StudySiteMember"]] = relationship(back_populates="site")
    subjects: Mapped[list["StudySubject"]] = relationship(back_populates="site")


class StudySiteMember(Base):
    __tablename__ = "study_site_members"
    __table_args__ = (
        UniqueConstraint("site_id", "user_id", name="uq_study_site_members_user"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    site_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("study_sites.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    site: Mapped[StudySite] = relationship(back_populates="members")


class StudySubject(Base):
    __tablename__ = "study_subjects"
    __table_args__ = (
        UniqueConstraint("study_id", "subject_code", name="uq_study_subjects_code"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    study_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clinical_studies.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    site_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("study_sites.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    subject_code: Mapped[str] = mapped_column(String(64), nullable=False)
    patient_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("patients.id", ondelete="RESTRICT"), nullable=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="enrolled")
    enrolled_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    study: Mapped["ClinicalStudy"] = relationship()
    site: Mapped[StudySite] = relationship(back_populates="subjects")
    visits: Mapped[list["StudyVisit"]] = relationship(back_populates="subject")


class VisitWindow(Base):
    __tablename__ = "visit_windows"
    __table_args__ = (
        UniqueConstraint("study_id", "visit_code", name="uq_visit_windows_code"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    study_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clinical_studies.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    visit_code: Mapped[str] = mapped_column(String(64), nullable=False)
    target_day: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    minus_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    plus_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_baseline: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    study: Mapped["ClinicalStudy"] = relationship()


class StudyVisit(Base):
    __tablename__ = "study_visits"
    __table_args__ = (
        UniqueConstraint(
            "subject_id", "visit_code", "repeat_no", name="uq_study_visits_repeat",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    subject_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("study_subjects.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    visit_code: Mapped[str] = mapped_column(String(64), nullable=False)
    repeat_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    eye_exam_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("eye_exams.id", ondelete="RESTRICT"), nullable=True,
    )
    diagnosis_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("diagnoses.id", ondelete="RESTRICT"), nullable=True,
    )
    window_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("visit_windows.id", ondelete="RESTRICT"), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    subject: Mapped[StudySubject] = relationship(back_populates="visits")
    window: Mapped[VisitWindow | None] = relationship()
    responses: Mapped[list["QuestionnaireResponse"]] = relationship(back_populates="visit")
    observations: Mapped[list["ClinicalObservation"]] = relationship(back_populates="visit")


class QuestionnaireDefinition(Base):
    __tablename__ = "questionnaire_definitions"
    __table_args__ = (
        UniqueConstraint("study_id", "code", name="uq_questionnaire_definitions_code"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    study_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clinical_studies.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    study: Mapped["ClinicalStudy"] = relationship()
    versions: Mapped[list["QuestionnaireVersion"]] = relationship(back_populates="definition")


class QuestionnaireVersion(Base):
    __tablename__ = "questionnaire_versions"
    __table_args__ = (
        UniqueConstraint(
            "definition_id", "version_number", name="uq_questionnaire_versions_number",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    definition_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("questionnaire_definitions.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    items_json: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    definition: Mapped[QuestionnaireDefinition] = relationship(back_populates="versions")
    responses: Mapped[list["QuestionnaireResponse"]] = relationship(back_populates="version")


class VisitFormAssignment(Base):
    """Visit 코드에 연결하는 연구별 폼. 문항 내용은 definition 버전에 있다."""

    __tablename__ = "visit_form_assignments"
    __table_args__ = (
        UniqueConstraint(
            "study_id", "visit_code", "definition_id", name="uq_visit_form_assignment",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    study_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clinical_studies.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    visit_code: Mapped[str] = mapped_column(String(64), nullable=False)
    definition_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("questionnaire_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


class QuestionnaireResponse(Base):
    __tablename__ = "questionnaire_responses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("questionnaire_versions.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    visit_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("study_visits.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    correction_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    finalized_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_by: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    supersedes_response_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("questionnaire_responses.id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    version: Mapped[QuestionnaireVersion] = relationship(back_populates="responses")
    visit: Mapped[StudyVisit] = relationship(back_populates="responses")
    items: Mapped[list["QuestionnaireResponseItem"]] = relationship(back_populates="response")


class QuestionnaireResponseItem(Base):
    __tablename__ = "questionnaire_response_items"
    __table_args__ = (
        UniqueConstraint(
            "response_id", "item_code", name="uq_questionnaire_response_items_code",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    response_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("questionnaire_responses.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    item_code: Mapped[str] = mapped_column(String(64), nullable=False)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    response: Mapped[QuestionnaireResponse] = relationship(back_populates="items")


class ClinicalObservation(Base):
    """원본 측정. 확정 행은 고치지 않고 revision 이 증가한 후속 행을 추가한다."""

    __tablename__ = "clinical_observations"
    __table_args__ = (
        UniqueConstraint(
            "visit_id", "code", "laterality", "method", "repeat_index", "revision",
            name="uq_clinical_observations_revision",
        ),
        Index("ix_clinical_observations_visit_code", "visit_id", "code"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    visit_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("study_visits.id", ondelete="RESTRICT"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    laterality: Mapped[str] = mapped_column(String(8), nullable=False, default="NA")
    method: Mapped[str] = mapped_column(String(32), nullable=False, default="NA")
    repeat_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    value_number: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    source_observation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("clinical_observations.id", ondelete="RESTRICT"),
        nullable=True,
    )
    supersedes_observation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("clinical_observations.id", ondelete="RESTRICT"),
        nullable=True,
    )
    eye_exam_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("eye_exams.id", ondelete="RESTRICT"), nullable=True,
    )
    model_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    record_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="final", server_default="final",
    )
    correction_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    finalized_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_by: Mapped[str] = mapped_column(String(64), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    row_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    visit: Mapped[StudyVisit] = relationship(back_populates="observations")


class DataQualityRule(Base):
    __tablename__ = "data_quality_rules"
    __table_args__ = (
        UniqueConstraint(
            "study_id", "code", "version_number", name="uq_data_quality_rules_version",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    study_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clinical_studies.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    logic_json: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    study: Mapped["ClinicalStudy"] = relationship()


class DataQualityFinding(Base):
    __tablename__ = "data_quality_findings"
    __table_args__ = (
        Index("ix_data_quality_findings_fingerprint", "fingerprint"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    rule_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("data_quality_rules.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False)
    study_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clinical_studies.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    subject_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("study_subjects.id", ondelete="RESTRICT"), nullable=True,
    )
    visit_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("study_visits.id", ondelete="RESTRICT"), nullable=True,
    )
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    message_code: Mapped[str] = mapped_column(String(64), nullable=False)
    source_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evaluation_scope: Mapped[str] = mapped_column(
        String(16), nullable=False, default="study", server_default="study",
    )
    evaluation_scope_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    waive_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    rule: Mapped[DataQualityRule] = relationship()


class QualityEvaluationRun(Base):
    """한 번의 품질 검증 실행. 관찰 행은 만들지 않는다."""

    __tablename__ = "quality_evaluation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    study_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clinical_studies.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    scope_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    trigger: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    actor_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    finding_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ClinicalQuery(Base):
    """연구별 임상 질의. 상태 이력은 삭제하지 않는다."""

    __tablename__ = "clinical_queries"
    __table_args__ = (
        Index("ix_clinical_queries_study_status", "study_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    study_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clinical_studies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    site_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("study_sites.id", ondelete="RESTRICT"), nullable=True,
    )
    subject_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("study_subjects.id", ondelete="RESTRICT"), nullable=True,
    )
    visit_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("study_visits.id", ondelete="RESTRICT"), nullable=True,
    )
    definition_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("questionnaire_definitions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    observation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("clinical_observations.id", ondelete="RESTRICT"),
        nullable=True,
    )
    finding_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("data_quality_findings.id", ondelete="RESTRICT"),
        nullable=True,
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    assigned_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assigned_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    opened_by: Mapped[str] = mapped_column(String(64), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    events: Mapped[list["ClinicalQueryEvent"]] = relationship(back_populates="query")
    responses: Mapped[list["ClinicalQueryResponse"]] = relationship(back_populates="query")


class ClinicalQueryEvent(Base):
    __tablename__ = "clinical_query_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    query_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clinical_queries.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    detail_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    query: Mapped[ClinicalQuery] = relationship(back_populates="events")


class ClinicalQueryResponse(Base):
    __tablename__ = "clinical_query_responses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    query_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clinical_queries.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    author_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    query: Mapped[ClinicalQuery] = relationship(back_populates="responses")


class ClinicalAuditEvent(Base):
    __tablename__ = "clinical_audit_events"
    __table_args__ = (
        Index("ix_clinical_audit_events_study", "study_id", "occurred_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    study_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clinical_studies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    site_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("study_sites.id", ondelete="RESTRICT"), nullable=True,
    )
    actor_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    new_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class DataLockRecord(Base):
    """잠금 이행의 추가 전용 이력. 현재 상태는 data_lock_states 에 둔다."""

    __tablename__ = "data_lock_records"
    __table_args__ = (
        UniqueConstraint(
            "lock_state_id", "state_version", name="uq_data_lock_records_version",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    study_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clinical_studies.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    site_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("study_sites.id", ondelete="RESTRICT"), nullable=True,
    )
    lock_state_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    from_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    state_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unlock_request_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


class DataExportRecord(Base):
    __tablename__ = "data_export_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    study_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clinical_studies.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    site_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("study_sites.id", ondelete="RESTRICT"), nullable=True,
    )
    actor_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    filter_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="requested")
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )


class DataLockState(Base):
    """범위별 현재 잠금 상태. 관찰 record_status 와 별도다."""

    __tablename__ = "data_lock_states"
    __table_args__ = (
        UniqueConstraint(
            "study_id", "target_type", "target_id", name="uq_data_lock_states_target",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    study_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clinical_studies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    site_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("study_sites.id", ondelete="RESTRICT"), nullable=True,
    )
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    target_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


class DataUnlockRequest(Base):
    __tablename__ = "data_unlock_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    lock_state_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("data_lock_states.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    study_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clinical_studies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    site_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("study_sites.id", ondelete="RESTRICT"), nullable=True,
    )
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    lock_state_at_request: Mapped[str] = mapped_column(String(32), nullable=False)
    requesting_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StudyProtocolDefinition(Base):
    """연구별 준비도 정의. 특정 임상시험 규칙을 공통 서비스에 넣지 않는다."""

    __tablename__ = "study_protocol_definitions"
    __table_args__ = (
        UniqueConstraint(
            "study_id", "version_number", name="uq_study_protocol_definitions_version",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    study_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clinical_studies.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    requirements_json: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


class MonitoringIndicatorRun(Base):
    __tablename__ = "monitoring_indicator_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    study_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clinical_studies.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    protocol_definition_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("study_protocol_definitions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    actor_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


class MonitoringIndicator(Base):
    """원본 관찰과 분리된 결정적 지표. 예측값과 효능 주장을 담지 않는다."""

    __tablename__ = "monitoring_indicators"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("monitoring_indicator_runs.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    study_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clinical_studies.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    site_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("study_sites.id", ondelete="RESTRICT"), nullable=True,
    )
    subject_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("study_subjects.id", ondelete="RESTRICT"), nullable=True,
    )
    visit_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("study_visits.id", ondelete="RESTRICT"), nullable=True,
    )
    indicator_code: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
