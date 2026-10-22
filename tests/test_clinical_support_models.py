"""합성 SQLite 에서만 임상 지원 모델을 검증한다.

운영 데이터베이스, DeeVo, alembic upgrade 는 사용하지 않는다.
"""
from __future__ import annotations

import ast
import sys
import types
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if "models" not in sys.modules:
    _models = types.ModuleType("models")
    _models.__path__ = [str(_ROOT / "models")]  # type: ignore[attr-defined]
    sys.modules["models"] = _models

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from database import Base
from models.clinical import ClinicalStudy
from models.medical import Diagnosis, EyeExam, Patient
from models.clinical_support import (
    ClinicalAuditEvent,
    ClinicalObservation,
    DataExportRecord,
    DataLockRecord,
    DataQualityFinding,
    DataQualityRule,
    QuestionnaireDefinition,
    QuestionnaireResponse,
    QuestionnaireResponseItem,
    QuestionnaireVersion,
    StudySite,
    StudySiteMember,
    StudySubject,
    StudyVisit,
    VisitWindow,
)
from schemas.clinical import StudyOut
from schemas.clinical_support import ObservationRecord, SubjectRecord
from services.clinical_records import (
    add_quality_rule,
    add_site,
    add_site_member,
    create_study,
    define_questionnaire,
    enroll_subject,
    get_study,
    open_visit,
    publish_questionnaire_version,
    record_observation,
    record_quality_finding,
    start_response,
    subject_columns,
    supersede_observation,
)

_TABLES = [
    Patient.__table__,
    EyeExam.__table__,
    Diagnosis.__table__,
    ClinicalStudy.__table__,
    StudySite.__table__,
    StudySiteMember.__table__,
    StudySubject.__table__,
    VisitWindow.__table__,
    StudyVisit.__table__,
    QuestionnaireDefinition.__table__,
    QuestionnaireVersion.__table__,
    QuestionnaireResponse.__table__,
    QuestionnaireResponseItem.__table__,
    ClinicalObservation.__table__,
    DataQualityRule.__table__,
    DataQualityFinding.__table__,
    ClinicalAuditEvent.__table__,
    DataLockRecord.__table__,
    DataExportRecord.__table__,
]

_BANNED = {
    "name",
    "patient_name",
    "mrn",
    "chart_no",
    "medical_record_number",
    "resident_number",
    "treatment_arm",
    "allocation",
    "unblinded",
}


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_connection, _record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine, tables=_TABLES)
    db = sessionmaker(bind=engine)()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _case(session: Session):
    study = create_study(session, code="SYN-001", name="Synthetic", study_kind="prospective")
    site = add_site(session, study_id=study.id, site_code="S1", name="Synthetic Site", actor_user_id="u1")
    add_site_member(session, site_id=site.id, user_id="u1", role="coordinator", actor_user_id="u1")
    add_site_member(session, site_id=site.id, user_id="coord-1", role="coordinator", actor_user_id="u1")
    subject = enroll_subject(
        session, study_id=study.id, site_id=site.id, subject_code="SUB-1", actor_user_id="u1",
    )
    window = VisitWindow(
        study_id=study.id, visit_code="BASE", target_day=0, is_baseline=1,
    )
    session.add(window)
    session.flush()
    visit = open_visit(
        session,
        subject_id=subject.id,
        visit_code="BASE",
        occurred_on=date(2026, 1, 15),
        actor_user_id="u1",
        window_id=window.id,
    )
    return study, site, subject, window, visit


@pytest.mark.unit
def test_study_kind_defaults_to_dataset(session: Session) -> None:
    study = ClinicalStudy(code="DS-1", name="Existing cohort style")
    session.add(study)
    session.flush()
    assert study.study_kind == "dataset"
    assert study.protocol_version is None
    loaded = get_study(session, study.id)
    assert loaded is not None
    assert loaded.study_kind == "dataset"


@pytest.mark.unit
def test_existing_study_schema_remains_compatible(session: Session) -> None:
    study = create_study(session, code="LEGACY", name="Legacy name")
    viewed = StudyOut.model_validate(study)
    assert viewed.code == "LEGACY"
    assert viewed.name == "Legacy name"
    assert viewed.status == "draft"
    assert "study_kind" not in StudyOut.model_fields
    assert ClinicalStudy.memberships is not None


@pytest.mark.unit
def test_subject_code_is_unique_inside_one_study(session: Session) -> None:
    study_a = create_study(session, code="A", name="A")
    study_b = create_study(session, code="B", name="B")
    site_a = add_site(session, study_id=study_a.id, site_code="S", name="A site", actor_user_id="u1")
    site_b = add_site(session, study_id=study_b.id, site_code="S", name="B site", actor_user_id="u1")
    add_site_member(session, site_id=site_a.id, user_id="u1", role="coordinator", actor_user_id="u1")
    add_site_member(session, site_id=site_b.id, user_id="u1", role="coordinator", actor_user_id="u1")
    enroll_subject(
        session, study_id=study_a.id, site_id=site_a.id, subject_code="SAME", actor_user_id="u1",
    )
    enroll_subject(
        session, study_id=study_b.id, site_id=site_b.id, subject_code="SAME", actor_user_id="u1",
    )
    with pytest.raises(IntegrityError):
        enroll_subject(
            session, study_id=study_a.id, site_id=site_a.id, subject_code="SAME", actor_user_id="u1",
        )


@pytest.mark.unit
def test_subject_has_no_direct_identifiers() -> None:
    columns = subject_columns()
    assert "subject_code" in columns
    assert "patient_id" in columns
    assert _BANNED.isdisjoint(columns)
    record = SubjectRecord(
        id="s", study_id="st", site_id="si", subject_code="SUB-1", patient_id=None, status="enrolled",
    )
    assert _BANNED.isdisjoint(record.model_fields)


@pytest.mark.unit
def test_visit_relationships(session: Session) -> None:
    study, _site, subject, window, visit = _case(session)
    assert visit.subject.id == subject.id
    assert visit.subject.study_id == study.id
    assert visit.window is not None
    assert visit.window.visit_code == visit.visit_code
    assert visit.window.is_baseline == 1


@pytest.mark.unit
def test_questionnaire_version_relationship(session: Session) -> None:
    study, _site, _subject, _window, visit = _case(session)
    definition = define_questionnaire(
        session, study_id=study.id, code="OSDI", title="OSDI", actor_user_id="u1",
    )
    version = publish_questionnaire_version(
        session,
        definition_id=definition.id,
        version_number=1,
        items_json='[{"code":"Q1"}]',
        actor_user_id="u1",
    )
    response = start_response(
        session, version_id=version.id, visit_id=visit.id, recorded_by="u1",
    )
    assert response.version.version_number == 1
    assert response.version.definition.code == "OSDI"
    assert response.version.definition.study_id == study.id
    assert response.visit.id == visit.id
    assert response.status == "draft"


@pytest.mark.unit
def test_observation_provenance(session: Session) -> None:
    _study, _site, subject, _window, visit = _case(session)
    row = record_observation(
        session,
        visit_id=visit.id,
        code="TBUT",
        laterality="OD",
        repeat_index=1,
        value_number=8,
        unit="s",
        source="manual",
        recorded_by="coord-1",
    )
    assert row.revision == 1
    assert row.record_status == "final"
    assert row.row_hash
    assert row.recorded_by == "coord-1"
    assert row.visit.subject.id == subject.id
    viewed = ObservationRecord.model_validate(row)
    assert viewed.value_number == 8
    assert viewed.supersedes_observation_id is None


@pytest.mark.unit
def test_correction_creates_successor_and_keeps_original(session: Session) -> None:
    _study, _site, _subject, _window, visit = _case(session)
    original = record_observation(
        session,
        visit_id=visit.id,
        code="SCHIRMER",
        laterality="OS",
        method="without_anesthesia",
        value_number=7,
        unit="mm",
        recorded_by="coord-1",
    )
    original_id = original.id
    original_hash = original.row_hash
    add_site_member(
        session, site_id=_site.id, user_id="coord-2", role="coordinator", actor_user_id="u1",
    )
    successor = supersede_observation(
        session, original_id, recorded_by="coord-2", reason="재측정", value_number=9, unit="mm",
    )
    session.refresh(original)
    assert original.id == original_id
    assert float(original.value_number) == 7
    assert original.row_hash == original_hash
    assert original.revision == 1
    assert successor.revision == 2
    assert successor.supersedes_observation_id == original_id
    assert float(successor.value_number) == 9
    assert successor.row_hash != original.row_hash
    stored = session.get(ClinicalObservation, original_id)
    assert stored is not None
    assert float(stored.value_number) == 7


@pytest.mark.unit
def test_quality_finding_does_not_overwrite_observation(session: Session) -> None:
    study, _site, subject, _window, visit = _case(session)
    row = record_observation(
        session, visit_id=visit.id, code="TBUT", value_number=5, unit="s", recorded_by="coord-1",
    )
    before = (row.value_number, row.row_hash, row.revision)
    rule = add_quality_rule(
        session,
        study_id=study.id,
        code="INVALID_RANGE",
        version_number=1,
        severity="error",
        logic_json='{"max":60}',
    )
    finding = record_quality_finding(
        session,
        rule_id=rule.id,
        study_id=study.id,
        subject_id=subject.id,
        visit_id=visit.id,
        target_type="observation",
        target_id=row.id,
        fingerprint="fp-1",
        message_code="INVALID_RANGE",
        actor_user_id="u1",
    )
    session.refresh(row)
    assert (row.value_number, row.row_hash, row.revision) == before
    assert finding.target_id == row.id
    assert finding.status == "open"


@pytest.mark.unit
def test_migration_draft_is_additive() -> None:
    path = _ROOT / "alembic" / "versions" / "medi006_clinical_support.py"
    source = path.read_text(encoding="utf-8")
    module = ast.parse(source)
    revision = None
    down = None
    for node in module.body:
        target = getattr(node, "target", None)
        name = getattr(target, "id", None)
        if name == "revision" and isinstance(node, ast.AnnAssign) and isinstance(node.value, ast.Constant):
            revision = node.value.value
        if name == "down_revision" and isinstance(node, ast.AnnAssign) and isinstance(node.value, ast.Constant):
            down = node.value.value
    assert revision == "medi006_clinical_support"
    assert down == "medi004_billing"
    upgrade = source.split("def downgrade", 1)[0]
    for name in (
        "study_sites",
        "study_site_members",
        "study_subjects",
        "study_visits",
        "visit_windows",
        "questionnaire_definitions",
        "questionnaire_versions",
        "questionnaire_responses",
        "questionnaire_response_items",
        "clinical_observations",
        "data_quality_rules",
        "data_quality_findings",
        "clinical_audit_events",
        "data_lock_records",
        "data_export_records",
    ):
        assert f'"{name}"' in upgrade
    assert "op.drop_table" not in upgrade
    assert "treatment_arm" not in source
    assert 'server_default="dataset"' in upgrade
    assert "correction_reason" in upgrade
    assert "finalized_by" in upgrade
