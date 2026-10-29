"""설문 엔진, OSDI 채점, 개선 루프. 합성 데이터만 사용한다."""
from __future__ import annotations

import json
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
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from database import Base
from models.clinical import ClinicalStudy
from models.clinical_support import (
    AuditEventChain,
    ClinicalAuditEvent,
    DataLockState,
    EcrfEntry,
    EcrfSchemaVersion,
    ImprovementFinding,
    ProtocolDocument,
    QuestionnaireDefinition,
    QuestionnaireResponse,
    QuestionnaireResponseItem,
    QuestionnaireScoreResult,
    QuestionnaireVersion,
    StudySite,
    StudySiteMember,
    StudySubject,
    StudyVisit,
    VisitFormAssignment,
    VisitWindow,
)
from models.medical import Diagnosis, EyeExam, Patient
from services.architecture_evidence import build_architecture_evidence, validate_evidence
from services.clinical_records import (
    ClinicalRecordError,
    add_site,
    add_site_member,
    create_study,
    enroll_subject,
    open_visit,
)
from services.improvement_loop import record_finding, transition_finding
from services.protocol_ecrf import register_protocol
from services.questionnaire_engine import (
    compare_questionnaire_versions,
    finalize_questionnaire_response,
    generate_osdi_draft,
    open_questionnaire_response,
    questionnaire_stats,
    record_questionnaire_item,
    score_osdi_response,
)

_SHA13 = "39c51490afb38c8b44aebbaaa4a5bb9186e29d29292fb1726138462272fbff91"
_SHA110 = "9e24fcedbd869e4e2b88d8b33e32acf617d4fd541199c78cd4c75d6444e2ac44"
_TABLES = [
    Patient.__table__, EyeExam.__table__, Diagnosis.__table__, ClinicalStudy.__table__,
    StudySite.__table__, StudySiteMember.__table__, VisitWindow.__table__,
    StudySubject.__table__, StudyVisit.__table__, ClinicalAuditEvent.__table__,
    DataLockState.__table__, ProtocolDocument.__table__, EcrfSchemaVersion.__table__,
    EcrfEntry.__table__, AuditEventChain.__table__, QuestionnaireDefinition.__table__,
    QuestionnaireVersion.__table__, VisitFormAssignment.__table__,
    QuestionnaireResponse.__table__, QuestionnaireResponseItem.__table__,
    QuestionnaireScoreResult.__table__, ImprovementFinding.__table__,
]


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
    study = create_study(session, code="SYN-Q", name="synthetic")
    site = add_site(session, study_id=study.id, site_code="S1", name="Site", actor_user_id="doc")
    add_site_member(session, site_id=site.id, user_id="doc", role="doctor", actor_user_id="doc")
    subject = enroll_subject(session, study_id=study.id, site_id=site.id, subject_code="SYN-01", actor_user_id="doc")
    visit = open_visit(session, subject_id=subject.id, visit_code="V1", occurred_on=date(2026, 3, 2), actor_user_id="doc")
    return study, site, subject, visit


def test_osdi_draft_score_stats_and_amendment(session: Session):
    study, site, _subject, visit = _seed(session)
    doc13 = register_protocol(
        session, study_id=study.id, site_id=site.id, actor_user_id="doc", actor_role="doctor",
        version_label="1.3", source_sha256=_SHA13, document_date="2025-05-26",
        source_present=True, source_reference="local protocol pdf",
    )
    draft13 = generate_osdi_draft(
        session, study_id=study.id, site_id=site.id, actor_user_id="doc", actor_role="doctor",
        document_id=doc13.id,
    )
    doc110 = register_protocol(
        session, study_id=study.id, site_id=site.id, actor_user_id="doc", actor_role="doctor",
        version_label="1.10", source_sha256=_SHA110, document_date="2026-07-01",
        source_present=True, source_reference="local protocol pdf", parent_document_id=doc13.id,
    )
    draft110 = generate_osdi_draft(
        session, study_id=study.id, site_id=site.id, actor_user_id="doc", actor_role="doctor",
        document_id=doc110.id,
    )
    assert draft13["proposal"] is True
    assert "V5" in draft13["visits"]
    assert "V5" not in draft110["visits"]
    assert "V6" in draft110["visits"]
    response = open_questionnaire_response(
        session, version_id=draft13["version_id"], visit_id=visit.id,
        actor_user_id="doc", actor_role="doctor",
    )
    for index in range(1, 6):
        record_questionnaire_item(
            session, response_id=response.id, actor_user_id="doc", actor_role="doctor",
            item_code=f"OSQ{index}", value=2,
        )
    for index in range(6, 13):
        record_questionnaire_item(
            session, response_id=response.id, actor_user_id="doc", actor_role="doctor",
            item_code=f"OSQ{index}", value="NA",
        )
    finalize_questionnaire_response(
        session, response_id=response.id, actor_user_id="doc", actor_role="doctor",
    )
    score = score_osdi_response(
        session, response_id=response.id, actor_user_id="doc", actor_role="doctor",
    )
    assert score.answered_count == 5
    assert score.not_applicable_count == 7
    assert score.blank_count == 0
    assert float(score.calculated_score) == 50.0
    assert score.status == "ADVISORY"
    assert json.loads(score.evidence_json)["original_values_mutated"] is False
    assert session.get(QuestionnaireResponse, response.id).version_id == draft13["version_id"]
    report = compare_questionnaire_versions(
        session, study_id=study.id, earlier_id=draft13["version_id"], later_id=draft110["version_id"],
    )
    assert report["overwrites_responses"] is False
    changed = [row for row in report["changes"] if row["classification"] == "CHANGED_VISIT_SCHEDULE"]
    assert changed
    stats = questionnaire_stats(
        session, study_id=study.id, site_id=site.id, actor_user_id="doc",
    )
    assert stats["denominator_responses"] == 1
    assert stats["status_counts"]["final"] == 1
    assert stats["score_distributions"]["combined"] is False
    assert stats["blinding_preserved"] is True


def test_zero_answers_do_not_divide_and_audit_failure_rolls_back(session: Session, monkeypatch):
    study, site, _subject, visit = _seed(session)
    document = register_protocol(
        session, study_id=study.id, site_id=site.id, actor_user_id="doc", actor_role="doctor",
        version_label="1.10", source_sha256=_SHA110, document_date="2026-07-01",
        source_present=True, source_reference="local protocol pdf",
    )
    draft = generate_osdi_draft(
        session, study_id=study.id, site_id=site.id, actor_user_id="doc", actor_role="doctor",
        document_id=document.id,
    )
    response = open_questionnaire_response(
        session, version_id=draft["version_id"], visit_id=visit.id,
        actor_user_id="doc", actor_role="doctor",
    )
    score = score_osdi_response(
        session, response_id=response.id, actor_user_id="doc", actor_role="doctor",
    )
    assert score.calculated_score is None
    assert score.status == "INCOMPLETE"
    assert score.answered_count == 0

    def fail(*_args, **_kwargs):
        raise RuntimeError("audit failed")

    monkeypatch.setattr("services.clinical_records._append_audit_chain", fail)
    before = session.query(QuestionnaireResponseItem).count()
    with pytest.raises(RuntimeError):
        record_questionnaire_item(
            session, response_id=response.id, actor_user_id="doc", actor_role="doctor",
            item_code="OSQ1", value=1,
        )
    session.rollback()
    assert session.query(QuestionnaireResponseItem).count() == before


def test_osdi_scoring_edge_cases_and_lock(session: Session):
    study, site, _subject, visit = _seed(session)
    document = register_protocol(
        session, study_id=study.id, site_id=site.id, actor_user_id="doc", actor_role="doctor",
        version_label="1.10", source_sha256=_SHA110, document_date="2026-07-01",
        source_present=True, source_reference="local protocol pdf",
    )
    draft = generate_osdi_draft(
        session, study_id=study.id, site_id=site.id, actor_user_id="doc", actor_role="doctor",
        document_id=document.id,
    )
    response = open_questionnaire_response(
        session, version_id=draft["version_id"], visit_id=visit.id,
        actor_user_id="doc", actor_role="doctor",
    )
    record_questionnaire_item(
        session, response_id=response.id, actor_user_id="doc", actor_role="doctor",
        item_code="OSQ1", value=1,
    )
    record_questionnaire_item(
        session, response_id=response.id, actor_user_id="doc", actor_role="doctor",
        item_code="OSQ6", value="NA",
    )
    mixed = score_osdi_response(
        session, response_id=response.id, actor_user_id="doc", actor_role="doctor",
    )
    assert mixed.answered_count == 1
    assert mixed.not_applicable_count == 1
    assert mixed.blank_count == 10
    assert float(mixed.calculated_score) == 25.0
    with pytest.raises(ClinicalRecordError):
        record_questionnaire_item(
            session, response_id=response.id, actor_user_id="doc", actor_role="doctor",
            item_code="OSQ2", value=9,
        )
    first = score_osdi_response(
        session, response_id=response.id, actor_user_id="doc", actor_role="doctor",
    )
    second = score_osdi_response(
        session, response_id=response.id, actor_user_id="doc", actor_role="doctor",
    )
    assert second.revision == first.revision + 1
    assert float(second.calculated_score) == float(first.calculated_score)
    session.add(DataLockState(
        study_id=study.id, site_id=site.id, scope="visit", target_type="visit",
        target_id=visit.id, state="LOCKED", version=1,
    ))
    session.flush()
    with pytest.raises(ClinicalRecordError):
        record_questionnaire_item(
            session, response_id=response.id, actor_user_id="doc", actor_role="doctor",
            item_code="OSQ3", value=2,
        )


def test_improvement_loop_and_architecture_evidence(session: Session):
    finding = record_finding(
        session,
        finding_code="Q-001",
        source_analyzer="svg-analyzer",
        source_version="1.0",
        module_id="questionnaire_scoring",
        severity="medium",
        evidence={"check": "na-denominator"},
        proposed_correction="문서화된 NA 제외를 유지한다.",
    )
    transition_finding(session, finding.id, next_state="TRIAGED")
    transition_finding(session, finding.id, next_state="ACCEPTED", decision="ACCEPTED", decision_reason="타당")
    transition_finding(session, finding.id, next_state="IMPLEMENTED", fix_ref="local-worktree")
    transition_finding(
        session, finding.id, next_state="RETESTED",
        test_evidence="tests/test_questionnaire_engine.py::test_osdi_draft_score_stats_and_amendment",
    )
    closed = transition_finding(
        session, finding.id, next_state="CLOSED",
        test_evidence="tests/test_questionnaire_engine.py::test_osdi_draft_score_stats_and_amendment",
        reanalysis_outcome="PASS",
    )
    assert closed.state == "CLOSED"
    with pytest.raises(ClinicalRecordError):
        transition_finding(session, finding.id, next_state="TRIAGED")
    rejected = record_finding(
        session, finding_code="Q-002", source_analyzer="svg-analyzer", source_version="1.0",
        module_id="questionnaire_definition", severity="low", evidence={"note": "waive"},
        proposed_correction="해당 없음",
    )
    transition_finding(session, rejected.id, next_state="TRIAGED")
    transition_finding(session, rejected.id, next_state="REJECTED", decision="REJECTED", decision_reason="범위 밖")
    with pytest.raises(ClinicalRecordError):
        transition_finding(session, rejected.id, next_state="IMPLEMENTED")
    waived = record_finding(
        session, finding_code="Q-003", source_analyzer="svg-analyzer", source_version="1.0",
        module_id="questionnaire_definition", severity="low", evidence={"note": "no-reason"},
        proposed_correction="해당 없음",
    )
    transition_finding(session, waived.id, next_state="TRIAGED")
    transition_finding(session, waived.id, next_state="REJECTED", decision="REJECTED")
    with pytest.raises(ClinicalRecordError):
        transition_finding(session, waived.id, next_state="CLOSED")
    transition_finding(session, rejected.id, next_state="CLOSED")
    from services.architecture_evidence import resolve_schema_id
    evidence = build_architecture_evidence(test_results={"questionnaire": "passed"})
    assert validate_evidence(evidence) == []
    assert evidence["schema"] == "eyecare-architecture-evidence/1"
    assert resolve_schema_id("eyecare-architecture-evidence/v1")["accepted"] is False
    assert resolve_schema_id("eyecare-architecture-evidence/1")["accepted"] is True
    assert "patient_records" in evidence["eyecare_meta"]["exclusions"]
    scoring = next(row for row in evidence["modules"] if row["module_id"] == "questionnaire_scoring")
    assert scoring["audit_covered"] is True
    assert scoring["db_owns"] == ["questionnaire_score_results"]
    assert evidence["edges"][0]["kind"] == "declared"
