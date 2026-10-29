"""계획서 eCRF 초안과 개정 보존. 합성 행만 사용한다."""
from __future__ import annotations

import sys
import types
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SHARED = Path(r"C:\Tools\downloads\phase005-inspect\shared-libraries")
if _SHARED.is_dir() and str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))
if "models" not in sys.modules:
    _models = types.ModuleType("models")
    _models.__path__ = [str(_ROOT / "models")]
    sys.modules["models"] = _models

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from database import Base
from models.clinical import ClinicalStudy
from models.clinical_support import VisitWindow
from models.medical import Diagnosis, EyeExam, Patient
from models.clinical_support import (
    AuditEventChain,
    ClinicalAuditEvent,
    DataLockState,
    EcrfEntry,
    EcrfSchemaVersion,
    ProtocolDocument,
    StudySite,
    StudySiteMember,
    StudySubject,
    StudyVisit,
)
from services.clinical_records import (
    add_site,
    add_site_member,
    create_study,
    enroll_subject,
    open_visit,
    ClinicalRecordError,
)
from services.protocol_ecrf import (
    activate_schema,
    amendment_report,
    dry_run_mapping,
    generate_draft,
    register_form_catalog,
    register_protocol,
    render_schema,
    rollback_plan,
    save_entry,
    simulate_approval,
    verify_chain,
)

_TABLES = [
    Patient.__table__, EyeExam.__table__, Diagnosis.__table__, ClinicalStudy.__table__,
    StudySite.__table__, StudySiteMember.__table__, VisitWindow.__table__,
    StudySubject.__table__, StudyVisit.__table__, ClinicalAuditEvent.__table__,
    DataLockState.__table__, ProtocolDocument.__table__, EcrfSchemaVersion.__table__,
    EcrfEntry.__table__, AuditEventChain.__table__,
]
_SHA13 = "39c51490afb38c8b44aebbaaa4a5bb9186e29d29292fb1726138462272fbff91"
_SHA110 = "9e24fcedbd869e4e2b88d8b33e32acf617d4fd541199c78cd4c75d6444e2ac44"


@pytest.fixture()
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def _fk(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    Base.metadata.create_all(engine, tables=_TABLES)
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TRIGGER audit_event_chains_append_only_update
            BEFORE UPDATE ON audit_event_chains
            BEGIN
              SELECT RAISE(ABORT, 'append-only clinical history');
            END
            """
        ))
    with Session(engine) as db:
        yield db


def _seed(session: Session):
    study = create_study(session, code="SYN-ECRF", name="synthetic")
    site = add_site(session, study_id=study.id, site_code="S1", name="Site", actor_user_id="doc")
    add_site_member(session, site_id=site.id, user_id="doc", role="doctor", actor_user_id="doc")
    subject = enroll_subject(session, study_id=study.id, site_id=site.id, subject_code="SYN-01", actor_user_id="doc")
    visit = open_visit(session, subject_id=subject.id, visit_code="V1", occurred_on=date(2026, 3, 2), actor_user_id="doc")
    visit5 = open_visit(session, subject_id=subject.id, visit_code="V5", occurred_on=date(2026, 4, 2), actor_user_id="doc")
    return study, site, subject, visit, visit5


def _prepare(session, study, site, version, sha, date_text, parent=None):
    document = register_protocol(
        session, study_id=study.id, site_id=site.id, actor_user_id="doc", actor_role="doctor",
        version_label=version, source_sha256=sha, document_date=date_text, source_present=True,
        source_reference="local protocol pdf", parent_document_id=parent,
    )
    schema = generate_draft(
        session, study_id=study.id, site_id=site.id, actor_user_id="doc", actor_role="doctor",
        document_id=document.id,
    )
    simulate_approval(
        session, study_id=study.id, site_id=site.id, actor_user_id="doc", actor_role="doctor",
        document_id=document.id,
    )
    activate_schema(
        session, study_id=study.id, site_id=site.id, actor_user_id="doc", actor_role="doctor",
        schema_id=schema.id,
    )
    return document, schema


def test_versions_stay_distinct_and_audit_is_append_only(session: Session):
    study, site, subject, visit, visit5 = _seed(session)
    first, schema13 = _prepare(session, study, site, "1.3", _SHA13, "2025-05-26")
    second, schema110 = _prepare(session, study, site, "1.10", _SHA110, "2026-07-01", parent=first.id)
    left = save_entry(
        session, study_id=study.id, site_id=site.id, actor_user_id="doc", actor_role="doctor",
        schema_id=schema13.id, subject_id=subject.id, visit_id=visit5.id,
        logical_field_id="OSDI-SCORE", value_number=12.5, value_text=None,
    )
    right = save_entry(
        session, study_id=study.id, site_id=site.id, actor_user_id="doc", actor_role="doctor",
        schema_id=schema110.id, subject_id=subject.id, visit_id=visit.id,
        logical_field_id="TBUT-OD-REPEAT", value_number=4, value_text=None, repeat_index=1,
    )
    report = amendment_report(session, study_id=study.id, earlier_id=schema13.id, later_id=schema110.id)
    dry = dry_run_mapping(report)
    osdi = next(row for row in report["changes"] if row["logical_field_id"] == "OSDI-SCORE")
    tbut = next(row for row in report["changes"] if row["logical_field_id"] == "TBUT-OD-REPEAT")
    assert osdi["classification"] == "CHANGED_VISIT_SCHEDULE"
    assert "V5" in osdi["earlier_visits"] and "V5" not in osdi["later_visits"]
    assert "V6" in osdi["later_visits"]
    assert tbut["classification"] == "UNCHANGED"
    assert dry["writes"] == 0
    assert report["unresolved"] == ["FORMAL_SIGNATURE", "WINDOW_3_VS_7", "VISIT4_TREATMENT", "OSDI_ROUNDING"]
    assert left.protocol_version == "1.3"
    assert right.protocol_version == "1.10"
    assert session.get(EcrfEntry, left.id).value_number == left.value_number
    assert first.approval_status == "SIMULATED_APPROVAL"
    assert first.simulated_approval is True
    chain = verify_chain(session, study.id)
    assert chain["count"] >= 8
    assert chain["has_genesis"] is True
    with pytest.raises(Exception):
        session.execute(text("UPDATE audit_event_chains SET actor_role = 'changed'"))
        session.flush()
    session.rollback()


def test_locked_visit_and_bad_repeat_do_not_write(session: Session):
    study, site, subject, visit, _visit5 = _seed(session)
    _document, schema = _prepare(session, study, site, "1.10", _SHA110, "2026-07-01")
    session.add(DataLockState(
        study_id=study.id, site_id=site.id, scope="visit", target_type="visit",
        target_id=visit.id, state="LOCKED", version=1,
    ))
    session.flush()
    before = session.query(EcrfEntry).count()
    with pytest.raises(ClinicalRecordError):
        save_entry(
            session, study_id=study.id, site_id=site.id, actor_user_id="doc", actor_role="doctor",
            schema_id=schema.id, subject_id=subject.id, visit_id=visit.id,
            logical_field_id="TBUT-OD-REPEAT", value_number=4, value_text=None, repeat_index=4,
        )
    with pytest.raises(ClinicalRecordError):
        save_entry(
            session, study_id=study.id, site_id=site.id, actor_user_id="doc", actor_role="doctor",
            schema_id=schema.id, subject_id=subject.id, visit_id=visit.id,
            logical_field_id="TBUT-OD-REPEAT", value_number=4, value_text=None, repeat_index=1,
        )
    assert session.query(EcrfEntry).count() == before


def test_duplicate_revision_is_rejected(session: Session):
    study, site, subject, visit, _visit5 = _seed(session)
    _document, schema = _prepare(session, study, site, "1.10", _SHA110, "2026-07-01")
    save_entry(
        session, study_id=study.id, site_id=site.id, actor_user_id="doc", actor_role="doctor",
        schema_id=schema.id, subject_id=subject.id, visit_id=visit.id,
        logical_field_id="SCHIRMER-OD", value_number=5, value_text=None,
    )
    session.add(EcrfEntry(
        study_id=study.id, site_id=site.id, subject_id=subject.id, visit_id=visit.id,
        schema_version_id=schema.id, protocol_version="1.10", logical_field_id="SCHIRMER-OD",
        repeat_index=1, revision=1, unit="mm/5min", record_status="recorded", created_by="doc",
    ))
    with pytest.raises(IntegrityError):
        session.flush()


def test_removed_field_and_rollback_keep_original_value(session: Session):
    def builder(version: str):
        if version == "A":
            return ([{
                "logical_field_id": "TEMP",
                "code": "TEMP",
                "unit": "s",
                "value_kind": "number",
                "repeated": False,
                "visits": ["V1"],
                "allows_not_applicable": False,
            }], [])
        return ([], [])
    register_form_catalog("SYN-PROTO", builder)
    study, site, subject, visit, _visit5 = _seed(session)
    first = register_protocol(
        session, study_id=study.id, site_id=site.id, actor_user_id="doc", actor_role="doctor",
        version_label="A", source_sha256=_SHA13, document_date="2025-05-26", source_present=True,
        source_reference="synthetic catalog", protocol_identifier="SYN-PROTO",
    )
    earlier = generate_draft(
        session, study_id=study.id, site_id=site.id, actor_user_id="doc", actor_role="doctor", document_id=first.id,
    )
    entry = save_entry(
        session, study_id=study.id, site_id=site.id, actor_user_id="doc", actor_role="doctor",
        schema_id=earlier.id, subject_id=subject.id, visit_id=visit.id,
        logical_field_id="TEMP", value_number=3, value_text=None,
    )
    second = register_protocol(
        session, study_id=study.id, site_id=site.id, actor_user_id="doc", actor_role="doctor",
        version_label="B", source_sha256=_SHA110, document_date="2026-07-01", source_present=True,
        source_reference="synthetic catalog", protocol_identifier="SYN-PROTO", parent_document_id=first.id,
    )
    later = generate_draft(
        session, study_id=study.id, site_id=site.id, actor_user_id="doc", actor_role="doctor", document_id=second.id,
    )
    report = amendment_report(session, study_id=study.id, earlier_id=earlier.id, later_id=later.id)
    again = amendment_report(session, study_id=study.id, earlier_id=earlier.id, later_id=later.id)
    removed = next(row for row in report["changes"] if row["logical_field_id"] == "TEMP")
    assert removed["classification"] == "REMOVED"
    assert again["changes"] == report["changes"]
    assert rollback_plan(report)["writes"] == 0
    assert rollback_plan(again)["keep_schema_id"] == earlier.id
    assert session.get(EcrfEntry, entry.id).value_number == entry.value_number
    rendered = render_schema(earlier)
    assert rendered["fields"][0]["logical_field_id"] == "TEMP"
    assert render_schema(later)["fields"] == []


def test_audit_failure_does_not_keep_the_entry(session: Session, monkeypatch):
    study, site, subject, visit, _visit5 = _seed(session)
    _document, schema = _prepare(session, study, site, "1.10", _SHA110, "2026-07-01")

    def fail(*_args, **_kwargs):
        raise RuntimeError("audit failed")

    monkeypatch.setattr("services.clinical_records._append_audit_chain", fail)
    with pytest.raises(RuntimeError):
        save_entry(
            session, study_id=study.id, site_id=site.id, actor_user_id="doc", actor_role="doctor",
            schema_id=schema.id, subject_id=subject.id, visit_id=visit.id,
            logical_field_id="OSDI-SCORE", value_number=1, value_text=None,
        )
    session.rollback()
    assert session.query(EcrfEntry).count() == 0


def test_not_applicable_osdi_item_is_accepted(session: Session):
    study, site, subject, _visit, visit5 = _seed(session)
    _document, schema = _prepare(session, study, site, "1.3", _SHA13, "2025-05-26")
    entry = save_entry(
        session, study_id=study.id, site_id=site.id, actor_user_id="doc", actor_role="doctor",
        schema_id=schema.id, subject_id=subject.id, visit_id=visit5.id,
        logical_field_id="OSQ6", value_number=None, value_text="NA",
    )
    assert entry.value_text == "NA"
    assert entry.protocol_version == "1.3"
