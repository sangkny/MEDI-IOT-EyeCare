"""Phase 010 증례 대시보드. 합성 행만 사용한다."""
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
    _models.__path__ = [str(_ROOT / "models")]  # type: ignore[attr-defined]
    sys.modules["models"] = _models

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from database import Base
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
    ImportBatch,
    ImportDiscrepancy,
    ImportLink,
    ImportSource,
    ImportStagingRow,
    ImportValidationFinding,
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
from services.clinical_case_dashboard import build_case_dashboard, validate_case_export
from services.clinical_records import (
    ClinicalRecordError,
    add_site,
    add_site_member,
    create_draft_observation,
    create_study,
    enroll_subject,
    finalize_observation,
    open_visit,
)

_TABLES = [
    Patient.__table__, EyeExam.__table__, Diagnosis.__table__, ClinicalStudy.__table__,
    StudySite.__table__, StudySiteMember.__table__, StudySubject.__table__, StudyVisit.__table__,
    VisitWindow.__table__, QuestionnaireDefinition.__table__, QuestionnaireVersion.__table__,
    QuestionnaireResponse.__table__, QuestionnaireResponseItem.__table__, VisitFormAssignment.__table__,
    ClinicalObservation.__table__, ClinicalAuditEvent.__table__,
    DataQualityRule.__table__, DataQualityFinding.__table__, QualityEvaluationRun.__table__,
    ClinicalQuery.__table__, ClinicalQueryEvent.__table__, ClinicalQueryResponse.__table__,
    DataLockState.__table__, DataUnlockRequest.__table__, DataLockRecord.__table__,
    DataExportRecord.__table__, StudyProtocolDefinition.__table__,
    MonitoringIndicatorRun.__table__, MonitoringIndicator.__table__,
    ImportSource.__table__, ImportBatch.__table__, ImportStagingRow.__table__,
    ImportLink.__table__, ImportDiscrepancy.__table__, ImportValidationFinding.__table__,
]


def _db() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    event.listen(engine, "connect", lambda dbapi, _rec: dbapi.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine, tables=_TABLES)
    return Session(engine)


def _seed(db: Session):
    study = create_study(db, code="SYN-DASH", name="Synthetic dashboard", study_kind="prospective")
    site = add_site(db, study_id=study.id, site_code="S1", name="Synthetic site", actor_user_id="doc")
    add_site_member(db, site_id=site.id, user_id="doc", role="investigator", actor_user_id="doc")
    subject = enroll_subject(
        db, study_id=study.id, site_id=site.id, subject_code="SYN-01", actor_user_id="doc",
    )
    first = open_visit(
        db, subject_id=subject.id, visit_code="V1", occurred_on=date(2026, 3, 2), actor_user_id="doc",
    )
    second = open_visit(
        db, subject_id=subject.id, visit_code="V2", occurred_on=date(2026, 3, 3), actor_user_id="doc",
    )
    draft = create_draft_observation(
        db, visit_id=second.id, code="TBUT", recorded_by="doc", actor_user_id="doc",
        laterality="OD", method="repeat", repeat_index=1, value_number=8, unit="s", source="import",
    )
    final = create_draft_observation(
        db, visit_id=second.id, code="TBUT", recorded_by="doc", actor_user_id="doc",
        laterality="OD", method="reported_average", repeat_index=0, value_number=4, unit="s", source="import",
    )
    finalize_observation(db, final.id, actor_user_id="doc")
    db.commit()
    return study, site, first, draft


def test_dashboard_separates_status_and_keeps_safety_defaults():
    db = _db()
    try:
        study, site, first, draft = _seed(db)
        view = build_case_dashboard(db, study_id=study.id, site_id=site.id, actor_user_id="doc")
        assert view["safety"]["enable_r1"] is False
        assert view["safety"]["protocol_advisory_id"] is None
        assert view["safety"]["window_check"] is False
        assert view["safety"]["unapproved_rules_active"] is False
        assert view["safety"]["automatic_finalize"] is False
        assert view["safety"]["automatic_lock"] is False
        assert view["overview"]["observation_status"] == {"draft": 1, "final": 1, "other": 0}
        assert view["subjects"][0]["subject_code"] == "SYN-01"
        assert view["visits"][0]["visit_code"] == "V1"
        assert view["analytics"]["subject_series"] is None
        final_boxes = view["analytics"]["final_descriptive"]
        draft_boxes = view["analytics"]["draft_exploratory"]
        assert final_boxes[0]["population"] == "FINAL"
        assert final_boxes[0]["method"] == "reported_average"
        assert final_boxes[0]["visits"] == [{
            "visit_code": "V2", "n": 1, "min": 4.0, "q1": 4.0, "median": 4.0, "q3": 4.0, "max": 4.0,
        }]
        assert draft_boxes[0]["population"] == "DRAFT"
        assert draft_boxes[0]["method"] == "repeat"
        assert draft_boxes[0]["visits"][0]["median"] == 8.0
        assert all(item["population"] == "FINAL" for item in final_boxes)
        assert all(item["population"] == "DRAFT" for item in draft_boxes)
        tbut_v1 = next(item for item in view["analytics"]["coverage"] if item["code"] == "TBUT" and item["visit_code"] == "V1")
        assert tbut_v1["expected"] == 1
        assert tbut_v1["absent"] == 1
        blob = json.dumps(view)
        assert "patient_id" not in blob
        assert draft.id not in blob
        empty = validate_case_export(
            db, study_id=study.id, site_id=site.id, actor_user_id="doc", content=None,
        )
        assert empty["persisted"] is False
        assert empty["real_export_loaded"] is False
        assert db.query(ImportBatch).count() == 0
        with pytest.raises(ClinicalRecordError):
            build_case_dashboard(db, study_id=study.id, site_id=site.id, actor_user_id="outsider")
    finally:
        db.close()
        db.get_bind().dispose()


def test_case_dashboard_page_lists_required_sections():
    page = (_ROOT / "static" / "clinical-dashboard" / "index.html").read_text(encoding="utf-8")
    for section in ("overview", "subjects", "visits", "analytics", "quality", "imports"):
        assert f'id="{section}"' in page
    assert "207" not in page
    assert "759" not in page
    assert 'href="' not in page
    assert "src=" not in page
    assert "FINAL" in page
    assert "DRAFT / NON-FINAL" in page


def test_subject_series_keeps_draft_final_eyes_and_hides_allocation():
    db = _db()
    try:
        study, site, first, _draft = _seed(db)
        create_draft_observation(
            db, visit_id=first.id, code="TBUT", recorded_by="doc", actor_user_id="doc",
            laterality="OS", method="repeat", repeat_index=1, value_text="nonnumeric", unit="s", source="import",
        )
        visit_five = open_visit(
            db, subject_id=first.subject_id, visit_code="V5", occurred_on=date(2026, 4, 1), actor_user_id="doc",
        )
        visit_six = open_visit(
            db, subject_id=first.subject_id, visit_code="V6", occurred_on=date(2026, 4, 2), actor_user_id="doc",
        )
        create_draft_observation(
            db, visit_id=visit_six.id, code="OSDI_SCORE", recorded_by="doc", actor_user_id="doc",
            laterality="NA", method="score", repeat_index=1, value_number=12, unit="score", source="import",
        )
        create_draft_observation(
            db, visit_id=visit_five.id, code="RN", recorded_by="doc", actor_user_id="doc",
            value_text="ARM-X", source="import",
        )
        other = add_site(db, study_id=study.id, site_code="S2", name="Other", actor_user_id="doc")
        add_site_member(db, site_id=other.id, user_id="doc", role="investigator", actor_user_id="doc")
        hidden = enroll_subject(
            db, study_id=study.id, site_id=other.id, subject_code="SYN-99", actor_user_id="doc",
        )
        db.commit()
        view = build_case_dashboard(
            db, study_id=study.id, site_id=site.id, actor_user_id="doc", subject_code="SYN-01",
        )
        final_values = [point["value_number"] for point in view["analytics"]["subject_series"]["FINAL"]]
        draft_values = [point["value_number"] for point in view["analytics"]["subject_series"]["DRAFT"]]
        assert final_values == [4.0]
        assert 12 in draft_values
        assert 8.0 in draft_values
        assert all(point["record_status"] == "FINAL" for point in view["analytics"]["subject_series"]["FINAL"])
        assert all(point["record_status"] == "DRAFT" for point in view["analytics"]["subject_series"]["DRAFT"])
        assert all(point["recalculated"] is False for point in view["analytics"]["subject_series"]["DRAFT"])
        osdi = [item for item in view["analytics"]["coverage"] if item["code"] == "OSDI_SCORE"]
        assert "V5" not in {item["visit_code"] for item in osdi}
        assert any(item["visit_code"] == "V6" and item["numeric_draft"] == 1 for item in osdi)
        assert view["analytics"]["nonnumeric_count"] == 1
        assert view["analytics"]["osdi_recalculated"] is False
        assert view["visits"][0]["visit_code"] == "V1"
        assert view["visits"][-1]["visit_code"] == "V6"
        blob = json.dumps(view)
        assert "ARM-X" not in blob
        assert "SYN-99" not in blob
        assert hidden.id not in blob
        with pytest.raises(ClinicalRecordError):
            build_case_dashboard(
                db, study_id=study.id, site_id=site.id, actor_user_id="doc", subject_code="SYN-99",
            )
        with pytest.raises(ClinicalRecordError):
            build_case_dashboard(db, study_id="unknown-study", site_id=site.id, actor_user_id="doc")
    finally:
        db.close()
        db.get_bind().dispose()


def test_dashboard_http_rejects_unauthenticated_and_unauthorized_access():
    import asyncio
    import importlib.util

    from auth.jwt_handler import create_access_token
    from fastapi import FastAPI
    from sqlalchemy import event as sa_event
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool as AsyncStaticPool
    from starlette.testclient import TestClient

    from database import get_db

    spec = importlib.util.spec_from_file_location(
        "clinical_dashboard_api", _ROOT / "api" / "clinical_dashboard.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=AsyncStaticPool)
    sa_event.listen(engine.sync_engine, "connect", lambda dbapi, _rec: dbapi.execute("PRAGMA foreign_keys=ON"))

    async def _prepare() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(lambda sync: Base.metadata.create_all(sync, tables=_TABLES))

        def _fill(sync) -> tuple[str, str]:
            session = Session(bind=sync)
            study, site, _first, _draft = _seed(session)
            ids = (study.id, site.id)
            session.close()
            return ids

        async with engine.begin() as conn:
            return await conn.run_sync(_fill)

    study_id, site_id = asyncio.run(_prepare())
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _db():
        async with factory() as session:
            yield session

    app = FastAPI()
    app.include_router(module.page_router)
    app.include_router(module.router, prefix="/api/v1/clinical-support")
    app.dependency_overrides[get_db] = _db
    doctor = {"Authorization": f"Bearer {create_access_token(subject='doc', role='doctor')}"}
    with TestClient(app) as client:
        page = client.get("/clinical-dashboard")
        assert page.status_code == 200
        assert page.headers["content-type"].startswith("text/html")
        assert "증례 대시보드" in page.text
        denied = client.get(f"/api/v1/clinical-support/studies/{study_id}/case-dashboard", params={"site_id": site_id})
        assert denied.status_code == 401
        manager = {"Authorization": f"Bearer {create_access_token(subject='doc', role='manager')}"}
        forbidden = client.get(
            f"/api/v1/clinical-support/studies/{study_id}/case-dashboard",
            params={"site_id": site_id},
            headers=manager,
        )
        assert forbidden.status_code == 403
        outsider = {"Authorization": f"Bearer {create_access_token(subject='other', role='doctor')}"}
        blocked = client.get(
            f"/api/v1/clinical-support/studies/{study_id}/case-dashboard",
            params={"site_id": site_id},
            headers=outsider,
        )
        assert blocked.status_code == 403
        unknown = client.get(
            "/api/v1/clinical-support/studies/not-a-member-study/case-dashboard",
            params={"site_id": site_id},
            headers=doctor,
        )
        assert unknown.status_code == 400
        long_code = client.get(
            f"/api/v1/clinical-support/studies/{study_id}/case-dashboard",
            params={"site_id": site_id, "subject_code": "X" * 65},
            headers=doctor,
        )
        assert long_code.status_code == 422
        long_study = client.get(
            f"/api/v1/clinical-support/studies/{'S' * 40}/case-dashboard",
            params={"site_id": site_id},
            headers=doctor,
        )
        assert long_study.status_code == 422
        allowed = client.get(
            f"/api/v1/clinical-support/studies/{study_id}/case-dashboard",
            params={"site_id": site_id, "subject_code": "SYN-01"},
            headers=doctor,
        )
        assert allowed.status_code == 200
        assert allowed.headers["content-type"].startswith("application/json")
        assert allowed.json()["analytics"]["subject_series"]["FINAL"][0]["value_number"] == 4.0
        audit = client.get(
            f"/api/v1/clinical-support/studies/{study_id}/case-dashboard",
            params={"site_id": site_id, "subject_code": "SYN-01"},
            headers=outsider,
        )
        assert audit.status_code == 403
