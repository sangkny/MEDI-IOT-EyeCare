"""Phase 007 임상 질의와 품질 엔진. 합성 데이터만 사용한다."""
from __future__ import annotations

import os
import sys
import threading
import types
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def _prepend_shared_libraries() -> None:
    """SHARED_LIBRARIES_PATH가 있으면 그 경로를 먼저 쓴다."""
    raw = os.environ.get("SHARED_LIBRARIES_PATH", "").strip()
    candidates: list[Path] = []
    if raw:
        candidates.append(Path(raw))
    candidates.extend(
        [
            Path("/app/shared-libraries"),
            _ROOT / "shared-libraries",
            _ROOT.parent / "shared-libraries",
        ]
    )
    for path in candidates:
        if (path / "auth" / "policy.py").is_file():
            resolved = str(path.resolve())
            if resolved not in sys.path:
                sys.path.insert(0, resolved)
            return


_prepend_shared_libraries()
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
    DataQualityFinding,
    DataQualityRule,
    QualityEvaluationRun,
    QuestionnaireDefinition,
    QuestionnaireResponse,
    QuestionnaireResponseItem,
    QuestionnaireVersion,
    StudySite,
    StudySiteMember,
    StudySubject,
    StudyVisit,
    VisitFormAssignment,
    VisitWindow,
)
from models.medical import Diagnosis, EyeExam, Patient
from services.clinical_monitoring import completeness_score, deferred_prediction, reliability_indicator
from services.clinical_quality import (
    medi_des_001_rule_catalog,
    register_demonstration_rules,
    run_quality_rules,
)
from services.clinical_queries import (
    assign_query,
    correct_from_query,
    create_query,
    create_query_from_finding,
    get_query,
    list_query_history,
    list_queries,
    reopen_query,
    resolve_query,
    respond_to_query,
)
from services.clinical_records import (
    ClinicalRecordError,
    add_quality_rule,
    add_site,
    add_site_member,
    assign_visit_form,
    create_draft_observation,
    create_study,
    define_questionnaire,
    enroll_subject,
    finalize_observation,
    open_visit,
    publish_questionnaire_version,
    start_response,
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
    DataLockRecord.__table__, DataExportRecord.__table__,
]


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    event.listen(engine, "connect", lambda dbapi, _rec: dbapi.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine, tables=_TABLES)
    return Session(engine)


def _ready(db: Session, user_id: str = "doc-a", site_code: str = "A"):
    study = create_study(db, code=f"SYN-{site_code}-{user_id}", name="Synthetic", study_kind="prospective")
    site = add_site(db, study_id=study.id, site_code=site_code, name=site_code, actor_user_id=user_id)
    add_site_member(db, site_id=site.id, user_id=user_id, role="investigator", actor_user_id=user_id)
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


def test_query_lifecycle_history_and_illegal_transition() -> None:
    db = _session()
    study, _site, subject, visit = _ready(db)
    final = _final(db, visit, 4)
    before = (float(final.value_number), final.row_hash, final.revision)
    query = create_query(
        db, study_id=study.id, actor_user_id="doc-a", category="manual", severity="error",
        description="값을 확인", subject_id=subject.id, observation_id=final.id,
        assigned_user_id="doc-a",
    )
    assert query.status == "open"
    assign_query(
        db, query.id, actor_user_id="doc-a", reason="담당 지정", assigned_role="investigator",
    )
    assert query.assigned_role == "investigator"
    with pytest.raises(ClinicalRecordError, match="허용되지 않는"):
        resolve_query(db, query.id, actor_user_id="doc-a", reason="너무 이름")
    respond_to_query(db, query.id, actor_user_id="doc-a", body="재측정함")
    assert query.status == "answered"
    resolved = resolve_query(db, query.id, actor_user_id="doc-a", reason="정정 확인")
    db.refresh(final)
    assert resolved.status == "resolved"
    assert (float(final.value_number), final.row_hash, final.revision) == before
    with pytest.raises(ClinicalRecordError, match="허용되지 않는"):
        respond_to_query(db, query.id, actor_user_id="doc-a", body="추가")
    reopened = reopen_query(db, query.id, actor_user_id="doc-a", reason="추가 확인")
    assert reopened.status == "reopened"
    respond_to_query(db, query.id, actor_user_id="doc-a", body="유지")
    history = list_query_history(db, query.id, actor_user_id="doc-a")
    assert [row.to_status for row in history] == [
        "open", "open", "answered", "resolved", "reopened", "answered",
    ]
    assert db.scalar(select(ClinicalQueryResponse).where(ClinicalQueryResponse.query_id == query.id))
    db.close()


def test_unauthorized_and_cross_site_queries() -> None:
    db = _session()
    study, site_a, _subject_a, _visit_a = _ready(db, "doc-a", "A")
    site_b = add_site(db, study_id=study.id, site_code="B", name="B", actor_user_id="doc-a")
    add_site_member(db, site_id=site_b.id, user_id="doc-b", role="investigator", actor_user_id="doc-a")
    subject_b = enroll_subject(
        db, study_id=study.id, site_id=site_b.id, subject_code="SUB-B", actor_user_id="doc-b",
    )
    with pytest.raises(ClinicalRecordError, match="구성원"):
        create_query(
            db, study_id=study.id, actor_user_id="stranger", category="manual",
            severity="warning", description="외부", subject_id=subject_b.id,
        )
    query = create_query(
        db, study_id=study.id, actor_user_id="doc-b", category="manual",
        severity="warning", description="사이트 B", subject_id=subject_b.id,
    )
    with pytest.raises(ClinicalRecordError, match="구성원"):
        get_query(db, query.id, actor_user_id="doc-a")
    visible = list_queries(db, study_id=study.id, actor_user_id="doc-a", severity="warning")
    assert query.id not in {row.id for row in visible}
    own = list_queries(db, study_id=study.id, actor_user_id="doc-b", site_id=site_b.id, status="open")
    assert [row.id for row in own] == [query.id]
    assert site_a.id != site_b.id
    db.close()


def test_finding_link_correction_preserves_original() -> None:
    db = _session()
    study, _site, _subject, visit = _ready(db)
    final = _final(db, visit, 9)
    add_quality_rule(
        db, study_id=study.id, code="RANGE", version_number=1, severity="error",
        logic_json='{"kind":"numeric_range","code":"TBUT","min":0,"max":3}',
    )
    found = run_quality_rules(db, study_id=study.id, actor_user_id="doc-a")
    query = create_query_from_finding(db, found[0].id, actor_user_id="doc-a")
    assert query.finding_id == found[0].id
    assert query.observation_id == final.id
    successor = correct_from_query(
        db, query.id, actor_user_id="doc-a", reason="재측정", value_number=2,
    )
    db.refresh(final)
    assert float(final.value_number) == 9
    assert successor.revision == 2
    assert successor.supersedes_observation_id == final.id
    assert query.status == "open"
    again = run_quality_rules(db, study_id=study.id, actor_user_id="doc-a")
    assert again == []
    db.close()


def test_quality_rules_are_repeatable_and_do_not_overwrite() -> None:
    db = _session()
    study, _site, subject, first = _ready(db)
    later = open_visit(
        db, subject_id=subject.id, visit_code="V2", occurred_on=date(2026, 2, 1), actor_user_id="doc-a",
    )
    final = _final(db, first, 1, code="LEFT")
    _final(db, first, 0, code="RIGHT")
    broken = ClinicalObservation(
        visit_id=first.id, code="LEFT", laterality="NA", method="NA", repeat_index=1, revision=3,
        value_number=8, source="manual", record_status="final", recorded_by="doc-a",
        supersedes_observation_id=final.id, row_hash="broken-chain",
    )
    db.add(broken)
    db.flush()
    blank = ClinicalObservation(
        visit_id=first.id, code="BLANK", laterality="NA", method="NA", repeat_index=1, revision=1,
        value_number=None, value_text=None, source="manual", record_status="final",
        recorded_by="", finalized_by=None, row_hash="blank",
    )
    db.add(blank)
    db.flush()
    before = (final.row_hash, blank.row_hash)
    specs = [
        ("MISS", '{"kind":"missing_value","code":"BLANK"}'),
        ("DUP", '{"kind":"duplicate_observation","code":"LEFT"}'),
        ("REV", '{"kind":"revision_chain"}'),
        ("DATE", '{"kind":"visit_date_order","order":["V1","V2"]}'),
        ("PROV", '{"kind":"provenance"}'),
        ("CROSS", '{"kind":"cross_field","left_code":"LEFT","right_code":"RIGHT","relation":"lte"}'),
        ("NEED", '{"kind":"required_effective","code":"OSDI_SCORE"}'),
    ]
    for index, (code, logic) in enumerate(specs, start=1):
        add_quality_rule(
            db, study_id=study.id, code=code, version_number=1, severity="warning", logic_json=logic,
        )
    found = run_quality_rules(db, study_id=study.id, actor_user_id="doc-a", scope="subject", scope_id=subject.id)
    codes = {row.message_code for row in found}
    assert {"missing_value", "duplicate_observation", "revision_chain", "visit_date_order", "provenance", "cross_field", "required_effective"} <= codes
    db.refresh(final)
    db.refresh(blank)
    assert (final.row_hash, blank.row_hash) == before
    assert run_quality_rules(
        db, study_id=study.id, actor_user_id="doc-a", scope="subject", scope_id=subject.id,
    ) == []
    visit_only = run_quality_rules(
        db, study_id=study.id, actor_user_id="doc-a", scope="visit", scope_id=later.id,
    )
    assert all(row.visit_id == later.id for row in visit_only)
    db.close()


def test_incomplete_questionnaire_on_form_scope() -> None:
    db = _session()
    study, _site, _subject, visit = _ready(db)
    definition = define_questionnaire(
        db, study_id=study.id, code="OSDI", title="OSDI", actor_user_id="doc-a",
    )
    version = publish_questionnaire_version(
        db, definition_id=definition.id, version_number=1,
        items_json='[{"code":"Q1","required":true,"type":"number"}]', actor_user_id="doc-a",
    )
    start_response(db, version_id=version.id, visit_id=visit.id, recorded_by="doc-a", actor_user_id="doc-a")
    assign_visit_form(
        db, study_id=study.id, visit_code="V1", definition_id=definition.id, actor_user_id="doc-a",
    )
    add_quality_rule(
        db, study_id=study.id, code="FORM", version_number=1, severity="error",
        logic_json='{"kind":"questionnaire_incomplete","definition_code":"OSDI"}',
    )
    found = run_quality_rules(
        db, study_id=study.id, actor_user_id="doc-a", scope="form", scope_id=definition.id,
    )
    assert [row.message_code for row in found] == ["questionnaire_incomplete"]
    assert run_quality_rules(
        db, study_id=study.id, actor_user_id="doc-a", scope="form", scope_id=definition.id,
    ) == []
    db.close()


def test_blocked_catalog_has_no_threshold_and_prediction_is_separate() -> None:
    catalog = medi_des_001_rule_catalog()
    assert any(item["source_status"] == "BLOCKED_PENDING_SOURCE" for item in catalog)
    assert all("min" not in item["logic"] and "max" not in item["logic"] for item in catalog)
    assert all(item["logic"].get("topic") != "allocation" for item in catalog)
    db = _session()
    study, _site, _subject, visit = _ready(db)
    final = _final(db, visit, 12)
    registered = register_demonstration_rules(db, study_id=study.id)
    assert {row.code for row in registered} == {"TBUT_PRESENT", "SCHIRMER_PRESENT", "OSDI_PRESENT"}
    add_quality_rule(
        db, study_id=study.id, code="BLOCKED", version_number=1, severity="warning",
        logic_json='{"kind":"blocked_source","topic":"visit_timing","min":1,"max":2}',
    )
    before = final.row_hash
    run_quality_rules(db, study_id=study.id, actor_user_id="doc-a")
    db.refresh(final)
    assert final.row_hash == before
    score = completeness_score(db, study_id=study.id)
    indicator = reliability_indicator(db, study_id=study.id)
    prediction = deferred_prediction("measurement_anomaly")
    assert score["predicted_value"] is None
    assert indicator["predicted_value"] is None
    assert prediction == {"kind": "measurement_anomaly", "status": "DEFERRED", "model": None, "predicted_value": None}
    db.refresh(final)
    assert float(final.value_number) == 12
    db.close()


def test_query_api_requires_auth_and_filters() -> None:
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    # 동기 엔진은 HTTP 테스트의 async 엔진과 분리한다.
    del engine
    import asyncio
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    async_engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    event.listen(async_engine.sync_engine, "connect", lambda dbapi, _rec: dbapi.execute("PRAGMA foreign_keys=ON"))

    async def _create() -> None:
        async with async_engine.begin() as conn:
            await conn.run_sync(lambda sync: Base.metadata.create_all(sync, tables=_TABLES))

    asyncio.run(_create())
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
    doctor = {"Authorization": f"Bearer {create_access_token(subject='doc-a', role='doctor')}"}
    staff = {"Authorization": f"Bearer {create_access_token(subject='doc-a', role='staff')}"}
    with TestClient(app) as client:
        assert client.get("/api/v1/clinical-support/queries", params={"study_id": "x"}).status_code == 401
        study = client.post(
            "/api/v1/clinical-support/studies", headers=doctor,
            json={"code": "QAPI", "name": "Q", "study_kind": "prospective"},
        )
        study_id = study.json()["id"]
        site = client.post(
            f"/api/v1/clinical-support/studies/{study_id}/sites", headers=doctor,
            json={"site_code": "S", "name": "S"},
        )
        site_id = site.json()["id"]
        client.post(
            f"/api/v1/clinical-support/sites/{site_id}/members", headers=doctor,
            json={"user_id": "doc-a", "role": "investigator"},
        )
        subject = client.post(
            "/api/v1/clinical-support/subjects", headers=doctor,
            json={"study_id": study_id, "site_id": site_id, "subject_code": "S1"},
        )
        denied = client.post(
            "/api/v1/clinical-support/queries", headers=staff,
            json={
                "study_id": study_id, "category": "manual", "severity": "error",
                "description": "staff", "subject_id": subject.json()["id"],
            },
        )
        assert denied.status_code == 403
        created = client.post(
            "/api/v1/clinical-support/queries", headers=doctor,
            json={
                "study_id": study_id, "category": "manual", "severity": "error",
                "description": "확인", "subject_id": subject.json()["id"],
            },
        )
        assert created.status_code == 201
        query_id = created.json()["id"]
        listed = client.get(
            "/api/v1/clinical-support/queries", headers=doctor,
            params={"study_id": study_id, "status": "open", "severity": "error"},
        )
        assert listed.status_code == 200
        assert listed.json()[0]["id"] == query_id
        outsider = client.get(
            f"/api/v1/clinical-support/queries/{query_id}",
            headers={"Authorization": f"Bearer {create_access_token(subject='doc-b', role='doctor')}"},
        )
        assert outsider.status_code == 403


@pytest.mark.integration
def test_postgresql_query_and_migration_when_configured() -> None:
    url = os.environ.get("EYECARE_PG_URL", "")
    if not url.startswith("postgresql"):
        pytest.skip("일회용 PostgreSQL URL 없음")
    engine = create_engine(url)
    db = sessionmaker(bind=engine)()
    try:
        with engine.connect() as conn:
            names = {
                row[0]
                for row in conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))
            }
        assert "clinical_queries" in names
        assert "quality_evaluation_runs" in names
        study, _site, subject, visit = _ready(db, "pg-doc", "PG")
        final = _final(db, visit, 4, user_id="pg-doc")
        query = create_query(
            db, study_id=study.id, actor_user_id="pg-doc", category="manual",
            severity="error", description="pg", subject_id=subject.id, observation_id=final.id,
        )
        respond_to_query(db, query.id, actor_user_id="pg-doc", body="응답")
        db.commit()
        outcome: list[str] = []
        gate = threading.Barrier(2)

        def _resolve_once() -> None:
            local = sessionmaker(bind=engine)()
            try:
                gate.wait(timeout=5)
                resolve_query(local, query.id, actor_user_id="pg-doc", reason="동시 종료")
                local.commit()
                outcome.append("ok")
            except ClinicalRecordError:
                local.rollback()
                outcome.append("blocked")
            finally:
                local.close()

        workers = [threading.Thread(target=_resolve_once), threading.Thread(target=_resolve_once)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=10)
        assert sorted(outcome) == ["blocked", "ok"]
        check = sessionmaker(bind=engine)()
        saved = check.get(ClinicalObservation, final.id)
        assert saved is not None and float(saved.value_number) == 4
        check.close()
    finally:
        db.close()
        engine.dispose()
