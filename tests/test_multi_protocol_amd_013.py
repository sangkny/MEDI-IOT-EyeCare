"""MEDI-DES-001 and MEDI-AMD-001 coexistence PoC. Synthetic data only."""
from __future__ import annotations

import json
import sys
import types
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

_ROOT = Path(__file__).resolve().parents[1]
_SHARED = Path(r"C:\Tools\downloads\phase005-inspect\shared-libraries")
if _SHARED.is_dir() and str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))
if "models" not in sys.modules:
    _models = types.ModuleType("models")
    _models.__path__ = [str(_ROOT / "models")]
    sys.modules["models"] = _models

from database import Base
from models.clinical import ClinicalStudy
from models.clinical_support import (
    AuditEventChain,
    ClinicalAuditEvent,
    EcrfEntry,
    EcrfSchemaVersion,
    ProtocolDocument,
    StudySite,
    StudySiteMember,
    StudySubject,
    StudyVisit,
)
from models.medical import Diagnosis, EyeExam, Patient
from services.amd_protocol_catalog import SOURCE_SHA256 as AMD_SHA, install_amd_catalog
from services.amd_stats_poc import analyze, synthetic_cohort
from services.architecture_evidence import build_architecture_evidence, validate_evidence, write_offline_evidence
from services.clinical_records import add_site, add_site_member, create_study, enroll_subject, open_visit
from services.protocol_ecrf import generate_draft, register_protocol

_DES_SHA = "9e24fcedbd869e4e2b88d8b33e32acf617d4fd541199c78cd4c75d6444e2ac44"


@pytest.fixture()
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    tables = [
        ClinicalStudy.__table__, StudySite.__table__, StudySiteMember.__table__, StudySubject.__table__,
        StudyVisit.__table__, Patient.__table__, EyeExam.__table__, Diagnosis.__table__,
        ProtocolDocument.__table__, EcrfSchemaVersion.__table__, EcrfEntry.__table__,
        ClinicalAuditEvent.__table__, AuditEventChain.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)

    @event.listens_for(engine, "connect")
    def _sqlite_setup(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    with Session(engine) as db:
        db.info["link_audit_chain"] = True
        install_amd_catalog()
        yield db
        db.rollback()
    engine.dispose()


def _seed(session: Session, *, code: str, user: str = "doc"):
    study = create_study(session, code=code, name=code)
    site = add_site(session, study_id=study.id, site_code="S1", name="Site", actor_user_id=user)
    add_site_member(session, site_id=site.id, user_id=user, role="doctor", actor_user_id=user)
    subject = enroll_subject(session, study_id=study.id, site_id=site.id, subject_code=f"{code}-01", actor_user_id=user)
    visit = open_visit(session, subject_id=subject.id, visit_code="V2", occurred_on=date(2026, 8, 1), actor_user_id=user)
    session.flush()
    return study, site, subject, visit


def test_amd_draft_ecrf_and_des_coexistence(session: Session):
    des, des_site, _, _ = _seed(session, code="SYN-DES-013")
    amd, amd_site, amd_subject, amd_visit = _seed(session, code="SYN-AMD-013")

    des_doc = register_protocol(
        session, study_id=des.id, site_id=des_site.id, actor_user_id="doc", actor_role="doctor",
        version_label="1.10", source_sha256=_DES_SHA, document_date="2026-07-01",
        source_present=True, source_reference="local des pdf", protocol_identifier="MEDI-DES-001",
    )
    amd_doc = register_protocol(
        session, study_id=amd.id, site_id=amd_site.id, actor_user_id="doc", actor_role="doctor",
        version_label="0.1", source_sha256=AMD_SHA, document_date="2026-07-31",
        source_present=True, source_reference="local amd docx draft", protocol_identifier="MEDI-AMD-001",
    )
    des_schema = generate_draft(
        session, study_id=des.id, site_id=des_site.id, actor_user_id="doc", actor_role="doctor",
        document_id=des_doc.id,
    )
    amd_schema = generate_draft(
        session, study_id=amd.id, site_id=amd_site.id, actor_user_id="doc", actor_role="doctor",
        document_id=amd_doc.id,
    )
    des_body = json.loads(des_schema.definition_json)
    amd_body = json.loads(amd_schema.definition_json)
    assert des_body["protocol_identifier"] == "MEDI-DES-001"
    assert amd_body["protocol_identifier"] == "MEDI-AMD-001"
    assert des_schema.id != amd_schema.id
    assert any(f["form_code"] == "OSDI" for f in des_body["forms"])
    assert all(f["form_code"] != "OSDI" for f in amd_body["forms"])
    assert any(f["form_code"] == "BCVA" for f in amd_body["forms"])
    assert any(f["form_code"] == "OCT_DRUSEN" for f in amd_body["forms"])
    assert "AMD-SCHED-V6" in amd_body["unresolved"]
    assert "AMD-WAVE" in amd_body["unresolved"]
    assert amd_body["rules_active"] is False
    wave_field = next(f for f in amd_body["fields"] if f["logical_field_id"] == "TX_WAVELENGTHS")
    assert "590" in (wave_field.get("note") or "") or "AMD-WAVE" in (wave_field.get("note") or "")

    # Independent visits / no cross-study leakage via schema ownership
    assert des_schema.study_id == des.id
    assert amd_schema.study_id == amd.id
    amd_only = session.scalars(select(EcrfSchemaVersion).where(EcrfSchemaVersion.study_id == amd.id)).all()
    des_only = session.scalars(select(EcrfSchemaVersion).where(EcrfSchemaVersion.study_id == des.id)).all()
    assert {row.id for row in amd_only} == {amd_schema.id}
    assert {row.id for row in des_only} == {des_schema.id}
    assert amd_subject.study_id == amd.id
    assert amd_visit.subject_id == amd_subject.id


def test_amd_stats_poc_and_architecture_evidence(session: Session, tmp_path: Path):
    result = analyze(synthetic_cohort())
    assert result["disclaimer"] == "SYNTHETIC_PROOF_OF_CONCEPT_NOT_CLINICAL_EVIDENCE"
    assert result["study_eye_metadata_present"] is True
    assert result["missing_data_preserved"] is True
    assert set(result["populations"]["FAS"]) == {"SYN-A", "SYN-B"}
    assert "SYN-C" in result["populations"]["SS"]
    assert result["bcva_change_from_baseline"]["week5_visit3"]["n"] >= 1
    assert result["bcva_change_from_baseline"]["week9_visit5"]["missing"] >= 1

    evidence = build_architecture_evidence(test_results={"multi_protocol_amd_013": "passed"})
    assert validate_evidence(evidence) == []
    assert evidence["schema"] == "eyecare-architecture-evidence/1"
    path = write_offline_evidence(tmp_path / "architecture-evidence.json", test_results={"multi_protocol_amd_013": "passed"})
    assert path.exists()
