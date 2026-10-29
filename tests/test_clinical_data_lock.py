"""Phase 008 잠금, 감사, 준비도. 합성 데이터만 사용한다."""
from __future__ import annotations

import os
import sys
import threading
import types
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

_ROOT = Path(__file__).resolve().parents[1]
_SHARED = Path(r"C:\Tools\downloads\phase005-inspect\shared-libraries")
if _SHARED.is_dir() and str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))
if "models" not in sys.modules:
    _models = types.ModuleType("models")
    _models.__path__ = [str(_ROOT / "models")]  # type: ignore[attr-defined]
    sys.modules["models"] = _models

import importlib.util

import pytest
from auth.jwt_handler import create_access_token
from fastapi import FastAPI
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

_spec = importlib.util.spec_from_file_location(
    "clinical_support_api", _ROOT / "api" / "clinical_support.py",
)
if "clinical_support_api" not in sys.modules:
    _api = importlib.util.module_from_spec(_spec)
    assert _spec is not None and _spec.loader is not None
    sys.modules["clinical_support_api"] = _api
    _spec.loader.exec_module(_api)
router = sys.modules["clinical_support_api"].router

from database import Base, get_db
from models.clinical import ClinicalStudy
from models.clinical_support import (
    ClinicalAuditEvent,
    ClinicalObservation,
    ClinicalQuery,
    ClinicalQueryEvent,
    ClinicalQueryResponse,
    DataExportRecord,
    DataLockRecord,
    DataLockState,
    DataQualityFinding,
    DataQualityRule,
    DataUnlockRequest,
    MonitoringIndicator,
    MonitoringIndicatorRun,
    QualityEvaluationRun,
    QuestionnaireDefinition,
    QuestionnaireResponse,
    QuestionnaireResponseItem,
    QuestionnaireVersion,
    StudyProtocolDefinition,
    StudySite,
    StudySiteMember,
    StudySubject,
    StudyVisit,
    VisitFormAssignment,
    VisitWindow,
)
from models.medical import Diagnosis, EyeExam, Patient
from services.clinical_lock import (
    apply_lock,
    approve_unlock,
    evaluate_lock_readiness,
    list_clinical_audit,
    list_lock_history,
    request_lock,
    request_unlock,
)
from services.clinical_monitoring import ai_monitoring_handoff, compute_monitoring_indicators
from services.clinical_quality import run_quality_rules
from services.clinical_queries import create_query
from services.clinical_readiness import (
    approve_protocol_definition,
    evaluate_readiness,
    register_protocol_definition,
)
from services.clinical_records import (
    ClinicalRecordError,
    _hash,
    add_quality_rule,
    add_site,
    add_site_member,
    correct_observation,
    create_draft_observation,
    create_study,
    enroll_subject,
    finalize_observation,
    open_visit,
    record_quality_finding,
    verify_audit_integrity,
)

_TABLES = [
    Patient.__table__, EyeExam.__table__, Diagnosis.__table__, ClinicalStudy.__table__,
    StudySite.__table__, StudySiteMember.__table__, StudySubject.__table__,
    VisitWindow.__table__, StudyVisit.__table__, QuestionnaireDefinition.__table__,
    QuestionnaireVersion.__table__, QuestionnaireResponse.__table__,
    QuestionnaireResponseItem.__table__, VisitFormAssignment.__table__,
    ClinicalObservation.__table__, DataQualityRule.__table__, DataQualityFinding.__table__,
    QualityEvaluationRun.__table__, ClinicalQuery.__table__, ClinicalQueryEvent.__table__,
    ClinicalQueryResponse.__table__, ClinicalAuditEvent.__table__,
    DataLockState.__table__, DataUnlockRequest.__table__, DataLockRecord.__table__,
    DataExportRecord.__table__, StudyProtocolDefinition.__table__,
    MonitoringIndicatorRun.__table__, MonitoringIndicator.__table__,
]


def _engine(url: str = "sqlite://"):
    engine = create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    event.listen(engine, "connect", lambda dbapi, _rec: dbapi.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine, tables=_TABLES)
    return engine


def _session() -> Session:
    return Session(_engine())


def _ready(db: Session, user_id: str = "doc-a", site_code: str = "A", manager_id: str = "dm-a"):
    study = create_study(
        db, code=f"SYN-{site_code}-{user_id}-{manager_id}", name="Synthetic", study_kind="prospective",
    )
    site = add_site(db, study_id=study.id, site_code=site_code, name=site_code, actor_user_id=user_id)
    add_site_member(db, site_id=site.id, user_id=user_id, role="investigator", actor_user_id=user_id)
    add_site_member(db, site_id=site.id, user_id=manager_id, role="data_manager", actor_user_id=user_id)
    subject = enroll_subject(
        db, study_id=study.id, site_id=site.id, subject_code=f"SUB-{site_code}", actor_user_id=user_id,
    )
    visit = open_visit(
        db, subject_id=subject.id, visit_code="V1", occurred_on=date(2026, 3, 1), actor_user_id=user_id,
    )
    return study, site, subject, visit


def _final(db: Session, visit, value: float, user_id: str = "doc-a", code: str = "TBUT"):
    draft = create_draft_observation(
        db, visit_id=visit.id, code=code, laterality="NA", value_number=value, unit="s",
        recorded_by=user_id, actor_user_id=user_id,
    )
    return finalize_observation(db, draft.id, actor_user_id=user_id)


def _approve(db: Session, study_id: str, requirements: dict, actor: str = "dm-a"):
    row = register_protocol_definition(
        db, study_id=study_id, actor_user_id=actor, requirements=requirements,
    )
    return approve_protocol_definition(db, row.id, actor_user_id=actor)


def _revision_chain(current: str) -> list[str]:
    """적용된 개정에서 베이스까지 Alembic 스크립트 조상을 따라간다."""
    config = Config(str(_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_ROOT / "alembic"))
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()
    assert heads == [current]
    chain = [current]
    revision = current
    while True:
        down = script.get_revision(revision).down_revision
        assert not isinstance(down, tuple)
        if down is None:
            return chain
        chain.append(down)
        revision = down


def _base_requirements(**extra) -> dict:
    payload = {
        "required_observations": [{"code": "TBUT"}],
        "blocking_query_severities": ["error", "critical"],
        "blocking_finding_severities": ["error", "critical"],
    }
    payload.update(extra)
    return payload


def _lock_pair(db: Session, study_id: str, observation_id: str):
    request_lock(
        db, study_id=study_id, target_type="observation", target_id=observation_id,
        actor_user_id="dm-a", reason="검토 요청",
    )
    return apply_lock(
        db, study_id=study_id, target_type="observation", target_id=observation_id,
        actor_user_id="dm-a", reason="잠금",
    )


def test_services_do_not_embed_medi_des_rules() -> None:
    for name in ("clinical_lock.py", "clinical_readiness.py", "clinical_monitoring.py"):
        text = (_ROOT / "services" / name).read_text(encoding="utf-8")
        assert "MEDI-DES-001" not in text
    assert _hash({"b": 1, "a": 2}) == _hash({"a": 2, "b": 1})


def test_lock_eligibility() -> None:
    db = _session()
    study, _site, _subject, visit = _ready(db)
    final = _final(db, visit, 8)
    _approve(db, study.id, _base_requirements())
    run_quality_rules(db, study_id=study.id, actor_user_id="doc-a")
    before = evaluate_lock_readiness(
        db, study_id=study.id, target_type="observation", target_id=final.id, actor_user_id="dm-a",
    )
    assert before["status"] == "COMPLETE"
    assert before["clinically_validated"] is False
    assert before["lock_eligible"] is False
    request_lock(
        db, study_id=study.id, target_type="observation", target_id=final.id,
        actor_user_id="dm-a", reason="검토 요청",
    )
    ready = evaluate_lock_readiness(
        db, study_id=study.id, target_type="observation", target_id=final.id, actor_user_id="dm-a",
    )
    assert ready["lock_eligible"] is True
    assert ready["lock_state"] == "READY_FOR_REVIEW"
    assert ready["actor_authorized_to_apply"] is True
    investigator = evaluate_lock_readiness(
        db, study_id=study.id, target_type="observation", target_id=final.id, actor_user_id="doc-a",
    )
    assert investigator["actor_authorized_to_apply"] is False
    db.close()


def test_missing_required_records() -> None:
    db = _session()
    study, _site, subject, visit = _ready(db)
    _final(db, visit, 8)
    draft = create_draft_observation(
        db, visit_id=visit.id, code="SCHIRMER", value_number=None, value_text="draft",
        recorded_by="doc-a", actor_user_id="doc-a",
    )
    _approve(db, study.id, _base_requirements(
        required_observations=[{"code": "TBUT"}, {"code": "SCHIRMER"}],
        required_questionnaires=[{"definition_code": "FORM_A"}],
        required_visit_codes=["V1", "V2"],
    ))
    run_quality_rules(db, study_id=study.id, actor_user_id="doc-a")
    report = evaluate_readiness(
        db, study_id=study.id, target_type="subject", target_id=subject.id,
    )
    assert report["status"] == "INCOMPLETE"
    assert report["assessment_class"] == "OPERATIONAL_NOT_CLINICALLY_VALIDATED"
    assert any(item.startswith("missing_record:SCHIRMER") for item in report["failures"])
    assert any(item.startswith("missing_questionnaire:FORM_A") for item in report["failures"])
    assert "visit_incomplete:V2" in report["failures"]
    draft_report = evaluate_readiness(
        db, study_id=study.id, target_type="observation", target_id=draft.id,
    )
    assert draft_report["status"] == "INCOMPLETE"
    db.close()


def test_blocking_unresolved_query() -> None:
    db = _session()
    study, _site, subject, visit = _ready(db)
    final = _final(db, visit, 8)
    _approve(db, study.id, _base_requirements())
    run_quality_rules(db, study_id=study.id, actor_user_id="doc-a")
    query = create_query(
        db, study_id=study.id, actor_user_id="doc-a", category="manual", severity="error",
        description="확인", subject_id=subject.id, observation_id=final.id,
    )
    report = evaluate_readiness(
        db, study_id=study.id, target_type="observation", target_id=final.id,
    )
    assert report["status"] == "BLOCKED_BY_QUERY"
    assert report["checks"]["outstanding_blocking_queries"] == 1
    request_lock(
        db, study_id=study.id, target_type="observation", target_id=final.id,
        actor_user_id="dm-a", reason="검토",
    )
    with pytest.raises(ClinicalRecordError, match="BLOCKED_BY_QUERY"):
        apply_lock(
            db, study_id=study.id, target_type="observation", target_id=final.id,
            actor_user_id="dm-a", reason="잠금",
        )
    db.refresh(query)
    assert query.status == "open"
    db.close()


def test_blocking_quality_finding() -> None:
    db = _session()
    study, _site, _subject, visit = _ready(db)
    final = _final(db, visit, 8)
    rule = add_quality_rule(
        db, study_id=study.id, code="RANGE", version_number=1, severity="error",
        logic_json='{"kind":"required_effective","code":"TBUT"}',
    )
    _approve(db, study.id, _base_requirements())
    run_quality_rules(db, study_id=study.id, actor_user_id="doc-a")
    finding = record_quality_finding(
        db, rule_id=rule.id, study_id=study.id, target_type="observation", target_id=final.id,
        fingerprint="synthetic-finding", message_code="range", actor_user_id="doc-a",
        subject_id=visit.subject_id, visit_id=visit.id, source_revision=final.revision,
    )
    report = evaluate_readiness(
        db, study_id=study.id, target_type="observation", target_id=final.id,
    )
    assert report["status"] == "BLOCKED_BY_QUALITY"
    assert report["checks"]["outstanding_blocking_findings"] >= 1
    db.refresh(finding)
    assert finding.status == "open"
    db.refresh(final)
    assert float(final.value_number) == 8
    db.close()


def test_successful_lock_keeps_source_status() -> None:
    db = _session()
    study, _site, _subject, visit = _ready(db)
    final = _final(db, visit, 8)
    before = (final.record_status, final.row_hash, final.revision, float(final.value_number))
    _approve(db, study.id, _base_requirements())
    run_quality_rules(db, study_id=study.id, actor_user_id="doc-a")
    state = _lock_pair(db, study.id, final.id)
    db.refresh(final)
    assert state.state == "LOCKED"
    assert (final.record_status, final.row_hash, final.revision, float(final.value_number)) == before
    assert final.record_status != "LOCKED"
    db.close()


def test_repeated_lock_is_rejected() -> None:
    db = _session()
    study, _site, _subject, visit = _ready(db)
    final = _final(db, visit, 8)
    _approve(db, study.id, _base_requirements())
    run_quality_rules(db, study_id=study.id, actor_user_id="doc-a")
    _lock_pair(db, study.id, final.id)
    with pytest.raises(ClinicalRecordError, match="허용되지 않는 잠금 전이"):
        apply_lock(
            db, study_id=study.id, target_type="observation", target_id=final.id,
            actor_user_id="dm-a", reason="다시 잠금",
        )
    db.close()


def test_unlock_request_records_reason_and_actor() -> None:
    db = _session()
    study, _site, _subject, visit = _ready(db)
    final = _final(db, visit, 8)
    _approve(db, study.id, _base_requirements())
    run_quality_rules(db, study_id=study.id, actor_user_id="doc-a")
    _lock_pair(db, study.id, final.id)
    unlock = request_unlock(
        db, study_id=study.id, target_type="observation", target_id=final.id,
        actor_user_id="doc-a", reason="정정 필요", request_id="req-unlock-1",
    )
    assert unlock.requesting_user_id == "doc-a"
    assert unlock.reason == "정정 필요"
    assert unlock.lock_state_at_request == "LOCKED"
    assert unlock.status == "pending"
    assert unlock.requested_at is not None
    state = db.scalar(select(DataLockState).where(DataLockState.target_id == final.id))
    assert state is not None and state.state == "UNLOCK_REQUESTED"
    db.close()


def test_unauthorized_unlock_is_rejected() -> None:
    db = _session()
    study, site, _subject, visit = _ready(db)
    final = _final(db, visit, 8)
    _approve(db, study.id, _base_requirements())
    run_quality_rules(db, study_id=study.id, actor_user_id="doc-a")
    _lock_pair(db, study.id, final.id)
    unlock = request_unlock(
        db, study_id=study.id, target_type="observation", target_id=final.id,
        actor_user_id="doc-a", reason="정정 필요",
    )
    with pytest.raises(ClinicalRecordError, match="해제 승인 권한"):
        approve_unlock(db, unlock.id, actor_user_id="doc-a", reason="본인 승인")
    add_site_member(db, site_id=site.id, user_id="doc-c", role="investigator", actor_user_id="dm-a")
    with pytest.raises(ClinicalRecordError, match="잠금 권한"):
        approve_unlock(db, unlock.id, actor_user_id="doc-c", reason="조사자 승인")
    add_site_member(db, site_id=site.id, user_id="dm-b", role="data_manager", actor_user_id="dm-a")
    site_b = add_site(db, study_id=study.id, site_code="B", name="B", actor_user_id="dm-a")
    add_site_member(db, site_id=site_b.id, user_id="outsider", role="data_manager", actor_user_id="dm-a")
    with pytest.raises(ClinicalRecordError, match="구성원"):
        approve_unlock(db, unlock.id, actor_user_id="outsider", reason="다른 사이트")
    db.refresh(final)
    assert float(final.value_number) == 8
    db.close()


def test_unlock_approval_preserves_observation() -> None:
    db = _session()
    study, site, _subject, visit = _ready(db)
    final = _final(db, visit, 8)
    before = (final.row_hash, float(final.value_number))
    _approve(db, study.id, _base_requirements())
    run_quality_rules(db, study_id=study.id, actor_user_id="doc-a")
    _lock_pair(db, study.id, final.id)
    unlock = request_unlock(
        db, study_id=study.id, target_type="observation", target_id=final.id,
        actor_user_id="doc-a", reason="정정 필요",
    )
    add_site_member(db, site_id=site.id, user_id="dm-b", role="data_manager", actor_user_id="dm-a")
    state = approve_unlock(db, unlock.id, actor_user_id="dm-b", reason="승인")
    db.refresh(final)
    db.refresh(unlock)
    assert state.state == "UNLOCKED"
    assert unlock.status == "approved"
    assert (final.row_hash, float(final.value_number)) == before
    db.close()


def test_invalid_lock_transitions() -> None:
    db = _session()
    study, _site, _subject, visit = _ready(db)
    final = _final(db, visit, 8)
    _approve(db, study.id, _base_requirements())
    run_quality_rules(db, study_id=study.id, actor_user_id="doc-a")
    with pytest.raises(ClinicalRecordError, match="허용되지 않는 잠금 전이"):
        apply_lock(
            db, study_id=study.id, target_type="observation", target_id=final.id,
            actor_user_id="dm-a", reason="바로 잠금",
        )
    with pytest.raises(ClinicalRecordError, match="허용되지 않는 잠금 전이"):
        request_unlock(
            db, study_id=study.id, target_type="observation", target_id=final.id,
            actor_user_id="doc-a", reason="잠금 전 해제",
        )
    _lock_pair(db, study.id, final.id)
    with pytest.raises(ClinicalRecordError, match="허용되지 않는 잠금 전이"):
        request_lock(
            db, study_id=study.id, target_type="observation", target_id=final.id,
            actor_user_id="dm-a", reason="잠긴 뒤 요청",
        )
    db.close()


def test_cross_site_lock_is_denied() -> None:
    db = _session()
    study, _site, _subject, visit = _ready(db)
    final = _final(db, visit, 8)
    site_b = add_site(db, study_id=study.id, site_code="B", name="B", actor_user_id="dm-a")
    add_site_member(db, site_id=site_b.id, user_id="dm-b", role="data_manager", actor_user_id="dm-a")
    _approve(db, study.id, _base_requirements())
    with pytest.raises(ClinicalRecordError, match="구성원"):
        request_lock(
            db, study_id=study.id, target_type="observation", target_id=final.id,
            actor_user_id="dm-b", reason="다른 사이트",
        )
    db.close()


def test_locked_observation_cannot_be_corrected() -> None:
    db = _session()
    study, _site, _subject, visit = _ready(db)
    final = _final(db, visit, 8)
    before = (final.id, final.row_hash, float(final.value_number))
    _approve(db, study.id, _base_requirements())
    run_quality_rules(db, study_id=study.id, actor_user_id="doc-a")
    _lock_pair(db, study.id, final.id)
    with pytest.raises(ClinicalRecordError, match="잠긴 임상 데이터"):
        correct_observation(
            db, final.id, actor_user_id="doc-a", reason="잠금 중 정정", value_number=1,
        )
    db.refresh(final)
    assert (final.id, final.row_hash, float(final.value_number)) == before
    assert db.scalar(select(ClinicalObservation).where(ClinicalObservation.supersedes_observation_id == final.id)) is None
    db.close()


def test_audit_event_is_append_only_and_verifiable() -> None:
    db = _session()
    study, _site, _subject, visit = _ready(db)
    final = _final(db, visit, 8)
    _approve(db, study.id, _base_requirements())
    run_quality_rules(db, study_id=study.id, actor_user_id="doc-a")
    _lock_pair(db, study.id, final.id)
    events = list_clinical_audit(
        db, study_id=study.id, actor_user_id="dm-a",
        target_type="observation", target_id=final.id,
    )
    lock_events = [row for row in events if row.action == "lock_apply"]
    assert lock_events
    event = lock_events[-1]
    assert event.actor_user_id == "dm-a"
    assert event.previous_state == "READY_FOR_REVIEW"
    assert event.new_state == "LOCKED"
    assert event.reason == "잠금"
    assert event.request_id
    assert event.target_revision == final.revision
    assert event.site_id is not None
    checked = verify_audit_integrity(event)
    assert checked["matches"] is True
    assert checked["regulatory_compliance"] is False
    legacy = ClinicalAuditEvent(
        study_id=study.id, actor_user_id="doc-a", action="create", target_type="study",
        target_id=study.id, request_id="legacy", payload_hash="abc",
        occurred_at=datetime.now(timezone.utc),
    )
    legacy_check = verify_audit_integrity(legacy)
    assert legacy_check["status"] == "LEGACY_HASH_ONLY"
    assert legacy_check["regulatory_compliance"] is False
    db.close()


def test_audit_failure_rolls_back_lock_transition() -> None:
    db = _session()
    study, _site, _subject, visit = _ready(db)
    final = _final(db, visit, 8)
    _approve(db, study.id, _base_requirements())
    run_quality_rules(db, study_id=study.id, actor_user_id="doc-a")
    request_lock(
        db, study_id=study.id, target_type="observation", target_id=final.id,
        actor_user_id="dm-a", reason="검토",
    )

    def _boom(*_args, **_kwargs):
        raise ClinicalRecordError("감사 기록을 저장하지 못했습니다.")

    original = sys.modules["services.clinical_lock"]._audit
    sys.modules["services.clinical_lock"]._audit = _boom
    try:
        with pytest.raises(ClinicalRecordError, match="감사 기록"):
            apply_lock(
                db, study_id=study.id, target_type="observation", target_id=final.id,
                actor_user_id="dm-a", reason="잠금",
            )
    finally:
        sys.modules["services.clinical_lock"]._audit = original
    state = db.scalar(select(DataLockState).where(DataLockState.target_id == final.id))
    assert state is not None and state.state == "READY_FOR_REVIEW"
    db.close()


def test_concurrent_lock_attempts(tmp_path: Path) -> None:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'lock.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    event.listen(engine, "connect", lambda dbapi, _rec: dbapi.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine, tables=_TABLES)
    db = Session(engine)
    study, _site, _subject, visit = _ready(db)
    final = _final(db, visit, 8)
    _approve(db, study.id, _base_requirements())
    run_quality_rules(db, study_id=study.id, actor_user_id="doc-a")
    request_lock(
        db, study_id=study.id, target_type="observation", target_id=final.id,
        actor_user_id="dm-a", reason="검토",
    )
    db.commit()
    observation_id = final.id
    study_id = study.id
    db.close()
    outcome: list[str] = []
    gate = threading.Barrier(2)

    def _apply() -> None:
        local = Session(engine)
        try:
            gate.wait(timeout=5)
            apply_lock(
                local, study_id=study_id, target_type="observation", target_id=observation_id,
                actor_user_id="dm-a", reason="동시 잠금",
            )
            local.commit()
            outcome.append("ok")
        except ClinicalRecordError:
            local.rollback()
            outcome.append("blocked")
        finally:
            local.close()

    workers = [threading.Thread(target=_apply), threading.Thread(target=_apply)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=15)
    assert sorted(outcome) == ["blocked", "ok"]
    check = Session(engine)
    state = check.scalar(select(DataLockState).where(DataLockState.target_id == observation_id))
    assert state is not None and state.state == "LOCKED"
    saved = check.get(ClinicalObservation, observation_id)
    assert saved is not None and float(saved.value_number) == 8
    check.close()
    engine.dispose()


def test_readiness_without_approved_protocol() -> None:
    db = _session()
    study, _site, _subject, visit = _ready(db)
    final = _final(db, visit, 8)
    draft = register_protocol_definition(
        db, study_id=study.id, actor_user_id="dm-a", requirements=_base_requirements(),
    )
    assert draft.status == "draft"
    report = evaluate_readiness(
        db, study_id=study.id, target_type="observation", target_id=final.id,
    )
    assert report["status"] == "BLOCKED_PENDING_PROTOCOL"
    assert report["assessment_class"] == "NOT_ASSESSED"
    assert report["clinically_validated"] is False
    assert report["lock_eligible"] is False
    db.close()


def test_locked_history_remains_after_relock() -> None:
    db = _session()
    study, site, _subject, visit = _ready(db)
    final = _final(db, visit, 8)
    _approve(db, study.id, _base_requirements())
    run_quality_rules(db, study_id=study.id, actor_user_id="doc-a")
    _lock_pair(db, study.id, final.id)
    unlock = request_unlock(
        db, study_id=study.id, target_type="observation", target_id=final.id,
        actor_user_id="doc-a", reason="재검토",
    )
    add_site_member(db, site_id=site.id, user_id="dm-b", role="data_manager", actor_user_id="dm-a")
    approve_unlock(db, unlock.id, actor_user_id="dm-b", reason="승인")
    _lock_pair(db, study.id, final.id)
    history = list_lock_history(
        db, study_id=study.id, actor_user_id="dm-a",
        target_type="observation", target_id=final.id,
    )
    assert [row.to_state for row in history] == [
        "READY_FOR_REVIEW", "LOCKED", "UNLOCK_REQUESTED", "UNLOCKED", "READY_FOR_REVIEW", "LOCKED",
    ]
    assert len({row.id for row in history}) == 6
    db.refresh(final)
    assert float(final.value_number) == 8
    db.close()


def test_monitoring_indicators_do_not_change_observations() -> None:
    db = _session()
    study, _site, _subject, visit = _ready(db)
    final = _final(db, visit, 8)
    before = final.row_hash
    rows = compute_monitoring_indicators(db, study_id=study.id, actor_user_id="doc-a")
    assert {row.status for row in rows} == {"BLOCKED_PENDING_PROTOCOL"}
    assert all(ai_monitoring_handoff(row)["prediction"] is None for row in rows)
    assert all(ai_monitoring_handoff(row)["automatic_clinical_mutation"] is False for row in rows)
    db.refresh(final)
    assert final.row_hash == before
    _approve(db, study.id, _base_requirements(
        query_aging_days=14,
        recurrent_finding_min=2,
        correction_frequency_min=3,
    ))
    query = create_query(
        db, study_id=study.id, actor_user_id="doc-a", category="manual", severity="warning",
        description="오래됨", subject_id=visit.subject_id, observation_id=final.id,
    )
    query.opened_at = datetime.now(timezone.utc) - timedelta(days=30)
    db.flush()
    again = compute_monitoring_indicators(db, study_id=study.id, actor_user_id="doc-a")
    by_code = {row.indicator_code: row.status for row in again}
    assert by_code["UNRESOLVED_QUERY_AGING"] == "OPEN"
    assert by_code["INCONSISTENT_LONGITUDINAL_MEASUREMENT"] == "NOT_CONFIGURED"
    assert by_code["VISIT_SCHEDULING_DEVIATION"] == "NOT_CONFIGURED"
    db.refresh(final)
    db.refresh(query)
    assert final.row_hash == before
    assert query.status == "open"
    db.close()


def test_lock_api_authorization() -> None:
    import asyncio

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    async_engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    try:
        event.listen(async_engine.sync_engine, "connect", lambda dbapi, _rec: dbapi.execute("PRAGMA foreign_keys=ON"))

        def _seed(sync) -> tuple[str, str]:
            Base.metadata.create_all(sync, tables=_TABLES)
            db = Session(bind=sync)
            study, _site, _subject, visit = _ready(db)
            final = _final(db, visit, 8)
            _approve(db, study.id, _base_requirements())
            run_quality_rules(db, study_id=study.id, actor_user_id="doc-a")
            db.flush()
            return study.id, final.id

        async def _prepare() -> tuple[str, str]:
            async with async_engine.begin() as conn:
                return await conn.run_sync(_seed)

        study_id, observation_id = asyncio.run(_prepare())
        factory = async_sessionmaker(async_engine, expire_on_commit=False)

        async def _db():
            async with factory() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

        app = FastAPI()
        app.include_router(router, prefix="/api/v1/clinical-support")
        app.dependency_overrides[get_db] = _db
        doctor = {"Authorization": f"Bearer {create_access_token(subject='dm-a', role='doctor')}"}
        staff = {"Authorization": f"Bearer {create_access_token(subject='dm-a', role='staff')}"}
        with TestClient(app) as client:
            assert client.post(
                "/api/v1/clinical-support/locks/applications",
                json={
                    "study_id": study_id, "target_type": "observation",
                    "target_id": observation_id, "reason": "잠금",
                },
            ).status_code == 401
            denied = client.post(
                "/api/v1/clinical-support/locks/applications",
                headers=staff,
                json={
                    "study_id": study_id, "target_type": "observation",
                    "target_id": observation_id, "reason": "잠금",
                },
            )
            assert denied.status_code == 403
            requested = client.post(
                "/api/v1/clinical-support/locks/requests",
                headers=doctor,
                json={
                    "study_id": study_id, "target_type": "observation",
                    "target_id": observation_id, "reason": "검토",
                },
            )
            assert requested.status_code == 200
            applied = client.post(
                "/api/v1/clinical-support/locks/applications",
                headers=doctor,
                json={
                    "study_id": study_id, "target_type": "observation",
                    "target_id": observation_id, "reason": "잠금",
                },
            )
            assert applied.status_code == 200
            assert applied.json()["state"] == "LOCKED"
            outsider = client.get(
                "/api/v1/clinical-support/readiness",
                headers={"Authorization": f"Bearer {create_access_token(subject='other', role='doctor')}"},
                params={"study_id": study_id, "target_type": "observation", "target_id": observation_id},
            )
            assert outsider.status_code == 403
    finally:
        asyncio.run(async_engine.dispose())


@pytest.mark.integration
def test_postgresql_lock_and_migration_when_configured() -> None:
    url = os.environ.get("EYECARE_PG_URL", "")
    if not url.startswith("postgresql"):
        pytest.skip("일회용 PostgreSQL URL 없음")
    engine = create_engine(url)
    db = sessionmaker(bind=engine)()
    check = None
    try:
        with engine.connect() as conn:
            names = {
                row[0]
                for row in conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))
            }
            version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        chain = _revision_chain(version)
        assert version == "medi012_questionnaire_engine"
        assert chain.index("medi012_questionnaire_engine") < chain.index("medi011_protocol_ecrf_audit")
        assert chain.index("medi011_protocol_ecrf_audit") < chain.index("medi010_external_clinical_import")
        assert chain.index("medi010_external_clinical_import") < chain.index("medi009_clinical_data_lock")
        assert chain.index("medi009_clinical_data_lock") < chain.index("medi008_clinical_query")
        assert {"data_lock_states", "data_unlock_requests", "monitoring_indicators"} <= names
        study, site, _subject, visit = _ready(db, "pg-doc", "PG", "pg-dm")
        final = _final(db, visit, 4, user_id="pg-doc")
        _approve(db, study.id, _base_requirements(), actor="pg-dm")
        run_quality_rules(db, study_id=study.id, actor_user_id="pg-doc")
        request_lock(
            db, study_id=study.id, target_type="observation", target_id=final.id,
            actor_user_id="pg-dm", reason="검토",
        )
        study_id = study.id
        observation_id = final.id
        db.commit()
        outcome: list[str] = []
        gate = threading.Barrier(2)

        def _apply() -> None:
            local = sessionmaker(bind=engine)()
            try:
                gate.wait(timeout=5)
                apply_lock(
                    local, study_id=study_id, target_type="observation", target_id=observation_id,
                    actor_user_id="pg-dm", reason="동시 잠금",
                )
                local.commit()
                outcome.append("ok")
            except ClinicalRecordError:
                local.rollback()
                outcome.append("blocked")
            finally:
                local.close()

        workers = [threading.Thread(target=_apply), threading.Thread(target=_apply)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=15)
        assert sorted(outcome) == ["blocked", "ok"]
        check = sessionmaker(bind=engine)()
        saved = check.get(ClinicalObservation, observation_id)
        assert saved is not None and float(saved.value_number) == 4
        locked = check.scalar(select(DataLockState).where(DataLockState.target_id == observation_id))
        assert locked is not None and locked.state == "LOCKED"
        unlock = request_unlock(
            check, study_id=study_id, target_type="observation", target_id=observation_id,
            actor_user_id="pg-doc", reason="정정 필요",
        )
        released = approve_unlock(check, unlock.id, actor_user_id="pg-dm", reason="승인")
        check.commit()
        assert released.state == "UNLOCKED"
        assert float(check.get(ClinicalObservation, observation_id).value_number) == 4
        event_id = check.scalar(
            select(ClinicalAuditEvent.id).where(ClinicalAuditEvent.action == "lock_apply")
        )
        with pytest.raises(Exception):
            check.execute(
                text("UPDATE clinical_audit_events SET reason = 'changed' WHERE id = :id"),
                {"id": event_id},
            )
            check.commit()
        check.rollback()
        add_site_member(db, site_id=site.id, user_id="pg-dm2", role="data_manager", actor_user_id="pg-dm")
        db.commit()
    finally:
        if check is not None:
            check.rollback()
            check.close()
        db.close()
        engine.dispose()
