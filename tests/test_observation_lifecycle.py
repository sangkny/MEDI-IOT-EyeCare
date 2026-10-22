"""관찰 초안·확정·정정. 합성 SQLite가 기본이고, 일회용 PostgreSQL은 환경 변수가 있을 때만."""
from __future__ import annotations

import os
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
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from models.clinical import ClinicalStudy
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
from models.medical import Diagnosis, EyeExam, Patient
from services.clinical_records import (
    ClinicalRecordError,
    add_site,
    add_site_member,
    correct_observation,
    create_draft_observation,
    create_study,
    enroll_subject,
    finalize_observation,
    get_effective_observation,
    list_observation_history,
    open_visit,
    update_draft_observation,
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


def _engine(url: str = "sqlite://"):
    kwargs = {}
    if url.startswith("sqlite"):
        kwargs = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
    engine = create_engine(url, **kwargs)

    @event.listens_for(engine, "connect")
    def _fk(dbapi_connection, _record) -> None:
        if url.startswith("sqlite"):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


@pytest.fixture
def session() -> Session:
    engine = _engine()
    Base.metadata.create_all(engine, tables=_TABLES)
    db = sessionmaker(bind=engine)()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _ready(session: Session):
    study = create_study(session, code="LIFE-1", name="Lifecycle", study_kind="prospective")
    site = add_site(session, study_id=study.id, site_code="S1", name="Site", actor_user_id="coord")
    add_site_member(session, site_id=site.id, user_id="coord", role="coordinator", actor_user_id="coord")
    subject = enroll_subject(
        session, study_id=study.id, site_id=site.id, subject_code="SUB-1", actor_user_id="coord",
    )
    visit = open_visit(
        session,
        subject_id=subject.id,
        visit_code="BASE",
        occurred_on=date(2026, 2, 1),
        actor_user_id="coord",
    )
    return study, site, visit


@pytest.mark.unit
def test_draft_is_not_the_effective_record(session: Session) -> None:
    _study, _site, visit = _ready(session)
    draft = create_draft_observation(
        session, visit_id=visit.id, code="TBUT", laterality="OD",
        value_number=4, unit="s", recorded_by="coord", actor_user_id="coord",
    )
    assert draft.record_status == "draft"
    assert get_effective_observation(
        session, visit_id=visit.id, code="TBUT", laterality="OD",
    ) is None
    with pytest.raises(ClinicalRecordError):
        create_draft_observation(
            session, visit_id=visit.id, code="TBUT", laterality="OD",
            recorded_by="outsider", actor_user_id="outsider",
        )


@pytest.mark.unit
def test_draft_update_and_finalize(session: Session) -> None:
    _study, _site, visit = _ready(session)
    draft = create_draft_observation(
        session, visit_id=visit.id, code="SCHIRMER", laterality="OS", method="without_anesthesia",
        recorded_by="coord", actor_user_id="coord",
    )
    with pytest.raises(ClinicalRecordError):
        finalize_observation(session, draft.id, actor_user_id="coord")
    update_draft_observation(
        session, draft.id, actor_user_id="coord", value_number=6, unit="mm",
    )
    final = finalize_observation(session, draft.id, actor_user_id="coord")
    assert final.record_status == "final"
    assert final.finalized_by == "coord"
    assert final.finalized_at is not None
    assert float(final.value_number) == 6
    with pytest.raises(ClinicalRecordError):
        update_draft_observation(session, final.id, actor_user_id="coord", value_number=9)
    session.refresh(final)
    assert float(final.value_number) == 6
    effective = get_effective_observation(
        session, visit_id=visit.id, code="SCHIRMER", laterality="OS", method="without_anesthesia",
    )
    assert effective is not None
    assert effective.id == final.id


@pytest.mark.unit
def test_correction_requires_reason_and_preserves_prior(session: Session) -> None:
    _study, _site, visit = _ready(session)
    draft = create_draft_observation(
        session, visit_id=visit.id, code="TBUT", laterality="OD",
        value_number=8, unit="s", recorded_by="coord", actor_user_id="coord",
    )
    final = finalize_observation(session, draft.id, actor_user_id="coord")
    with pytest.raises(ClinicalRecordError):
        correct_observation(session, final.id, actor_user_id="coord", reason="  ", value_number=9)
    successor = correct_observation(
        session, final.id, actor_user_id="coord", reason="재측정", value_number=9,
    )
    session.refresh(final)
    assert float(final.value_number) == 8
    assert final.record_status == "final"
    assert successor.revision == 2
    assert successor.supersedes_observation_id == final.id
    assert successor.correction_reason == "재측정"
    assert successor.recorded_by == "coord"
    effective = get_effective_observation(
        session, visit_id=visit.id, code="TBUT", laterality="OD",
    )
    assert effective is not None
    assert effective.id == successor.id
    history = list_observation_history(
        session, visit_id=visit.id, code="TBUT", laterality="OD",
    )
    assert [row.revision for row in history] == [1, 2]
    audit = session.scalar(
        select_audit(session, successor.id)
    )
    assert audit is not None
    assert audit.actor_user_id == "coord"
    assert audit.action == "amend"


def select_audit(session: Session, target_id: str):
    from sqlalchemy import select
    return select(ClinicalAuditEvent).where(
        ClinicalAuditEvent.target_id == target_id,
        ClinicalAuditEvent.action == "amend",
    )


@pytest.mark.unit
def test_second_correction_of_the_old_revision_is_rejected(session: Session) -> None:
    _study, _site, visit = _ready(session)
    draft = create_draft_observation(
        session, visit_id=visit.id, code="TBUT", laterality="OS",
        value_number=3, unit="s", recorded_by="coord", actor_user_id="coord",
    )
    final = finalize_observation(session, draft.id, actor_user_id="coord")
    correct_observation(session, final.id, actor_user_id="coord", reason="첫째", value_number=4)
    with pytest.raises(ClinicalRecordError):
        correct_observation(session, final.id, actor_user_id="coord", reason="둘째", value_number=5)
    duplicate = ClinicalObservation(
        visit_id=final.visit_id,
        code=final.code,
        laterality=final.laterality,
        method=final.method,
        repeat_index=final.repeat_index,
        revision=2,
        value_number=7,
        source="manual",
        record_status="final",
        recorded_by="coord",
        row_hash="duplicate",
    )
    session.add(duplicate)
    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.unit
def test_dataset_study_still_defaults(session: Session) -> None:
    study = create_study(session, code="DS", name="Dataset")
    assert study.study_kind == "dataset"


@pytest.mark.integration
def test_postgresql_lifecycle_when_configured() -> None:
    url = os.environ.get("EYECARE_PG_URL", "")
    if not url.startswith("postgresql"):
        pytest.skip("일회용 PostgreSQL URL 없음")
    engine = _engine(url)
    db = sessionmaker(bind=engine)()
    try:
        with engine.connect() as conn:
            names = {
                row[0]
                for row in conn.execute(
                    text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
                )
            }
        assert "clinical_observations" in names
        assert "patients" in names
        _study, _site, visit = _ready(db)
        draft = create_draft_observation(
            db, visit_id=visit.id, code="TBUT", laterality="OD",
            value_number=5, unit="s", recorded_by="coord", actor_user_id="coord",
        )
        final = finalize_observation(db, draft.id, actor_user_id="coord")
        successor = correct_observation(
            db, final.id, actor_user_id="coord", reason="pg 재측정", value_number=6,
        )
        db.refresh(final)
        assert float(final.value_number) == 5
        assert successor.revision == 2
        db.rollback()
    finally:
        db.close()
        engine.dispose()
