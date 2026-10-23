"""임상 지원 HTTP. 합성 SQLite와 공유 인증만 사용한다."""
from __future__ import annotations

import os
import sys
import types
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def _prepend_shared_libraries() -> None:
    """Compose PYTHONPATH와 Alembic env.py와 같은 위치만 찾는다.

    SHARED_LIBRARIES_PATH가 있으면 그 경로를 먼저 쓴다.
    없으면 /app/shared-libraries, 저장소 안 shared-libraries,
    부모 projects/shared-libraries 순서로 첫 정책 모듈을 고른다.
    """
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
from sqlalchemy import create_engine, event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

_spec = importlib.util.spec_from_file_location(
    "clinical_support_api", _ROOT / "api" / "clinical_support.py",
)
_api = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["clinical_support_api"] = _api
_spec.loader.exec_module(_api)
router = _api.router
from database import Base, get_db
from models.clinical import ClinicalStudy
from models.clinical_support import (
    ClinicalAuditEvent,
    ClinicalObservation,
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
from services.clinical_quality import review_finding, run_quality_rules
from services.clinical_records import (
    add_quality_rule,
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
    StudySite.__table__, StudySiteMember.__table__, StudySubject.__table__,
    VisitWindow.__table__, StudyVisit.__table__, QuestionnaireDefinition.__table__,
    QuestionnaireVersion.__table__, QuestionnaireResponse.__table__,
    QuestionnaireResponseItem.__table__, VisitFormAssignment.__table__,
    ClinicalObservation.__table__, DataQualityRule.__table__, DataQualityFinding.__table__,
    QualityEvaluationRun.__table__,
    ClinicalAuditEvent.__table__, DataLockRecord.__table__, DataExportRecord.__table__,
]


def _auth(user_id: str, role: str) -> dict[str, str]:
    token = create_access_token(subject=user_id, role=role)
    return {"Authorization": f"Bearer {token}"}


def _app():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    event.listen(engine.sync_engine, "connect", lambda dbapi, _rec: dbapi.execute("PRAGMA foreign_keys=ON"))
    import asyncio
    async def _create() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(lambda sync: Base.metadata.create_all(sync, tables=_TABLES))
    asyncio.run(_create())
    factory = async_sessionmaker(engine, expire_on_commit=False)

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
    return app


@pytest.fixture
def client():
    app = _app()
    with TestClient(app) as http:
        yield http


def test_missing_token_is_401(client: TestClient) -> None:
    response = client.get("/api/v1/clinical-support/studies")
    assert response.status_code == 401


def test_staff_cannot_create_clinical_records(client: TestClient) -> None:
    response = client.post(
        "/api/v1/clinical-support/studies",
        headers=_auth("staff-1", "staff"),
        json={"code": "X", "name": "X", "study_kind": "dataset"},
    )
    assert response.status_code == 403


def test_authorized_lifecycle_and_cross_site_rejection(client: TestClient) -> None:
    doctor = _auth("doc-a", "doctor")
    created = client.post(
        "/api/v1/clinical-support/studies",
        headers=doctor,
        json={"code": "SYN", "name": "Synthetic", "study_kind": "prospective"},
    )
    assert created.status_code == 201
    study_id = created.json()["id"]
    assert created.json()["study_kind"] == "prospective"
    site = client.post(
        f"/api/v1/clinical-support/studies/{study_id}/sites",
        headers=doctor,
        json={"site_code": "S1", "name": "Site 1"},
    )
    assert site.status_code == 201
    site_id = site.json()["id"]
    member = client.post(
        f"/api/v1/clinical-support/sites/{site_id}/members",
        headers=doctor,
        json={"user_id": "doc-a", "role": "investigator"},
    )
    assert member.status_code == 201
    outsider = client.get(f"/api/v1/clinical-support/studies/{study_id}", headers=_auth("doc-b", "doctor"))
    assert outsider.status_code == 403
    listed = client.get("/api/v1/clinical-support/studies", headers=doctor)
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == study_id
    subject = client.post(
        "/api/v1/clinical-support/subjects",
        headers=doctor,
        json={"study_id": study_id, "site_id": site_id, "subject_code": "SUB-1"},
    )
    assert subject.status_code == 201
    subject_id = subject.json()["id"]
    blocked = client.get(
        f"/api/v1/clinical-support/subjects/{subject_id}",
        headers=_auth("doc-b", "doctor"),
    )
    assert blocked.status_code == 403
    visit = client.post(
        "/api/v1/clinical-support/visits",
        headers=doctor,
        json={"subject_id": subject_id, "visit_code": "BASE", "occurred_on": "2026-03-01"},
    )
    assert visit.status_code == 201
    visit_id = visit.json()["id"]
    draft = client.post(
        "/api/v1/clinical-support/observations/drafts",
        headers=doctor,
        json={"visit_id": visit_id, "code": "TBUT", "laterality": "OD", "unit": "s"},
    )
    assert draft.status_code == 201
    draft_id = draft.json()["id"]
    assert draft.json()["record_status"] == "draft"
    missing = client.post(
        f"/api/v1/clinical-support/observations/{draft_id}/finalize",
        headers=doctor,
    )
    assert missing.status_code == 400
    updated = client.patch(
        f"/api/v1/clinical-support/observations/{draft_id}",
        headers=doctor,
        json={"value_number": 8},
    )
    assert updated.status_code == 200
    final = client.post(
        f"/api/v1/clinical-support/observations/{draft_id}/finalize",
        headers=doctor,
    )
    assert final.status_code == 200
    assert final.json()["record_status"] == "final"
    immutable = client.patch(
        f"/api/v1/clinical-support/observations/{draft_id}",
        headers=doctor,
        json={"value_number": 1},
    )
    assert immutable.status_code == 400
    no_reason = client.post(
        f"/api/v1/clinical-support/observations/{draft_id}/corrections",
        headers=doctor,
        json={"reason": " ", "value_number": 9},
    )
    assert no_reason.status_code == 400
    corrected = client.post(
        f"/api/v1/clinical-support/observations/{draft_id}/corrections",
        headers=doctor,
        json={"reason": "재측정", "value_number": 9},
    )
    assert corrected.status_code == 200
    assert corrected.json()["revision"] == 2
    history = client.get(
        "/api/v1/clinical-support/observations/history",
        headers=doctor,
        params={"visit_id": visit_id, "code": "TBUT", "laterality": "OD"},
    )
    assert history.status_code == 200
    assert [row["revision"] for row in history.json()] == [1, 2]
    effective = client.get(
        "/api/v1/clinical-support/observations/effective",
        headers=doctor,
        params={"visit_id": visit_id, "code": "TBUT", "laterality": "OD"},
    )
    assert effective.status_code == 200
    assert effective.json()["revision"] == 2
    form = client.post(
        "/api/v1/clinical-support/questionnaires",
        headers=doctor,
        json={"study_id": study_id, "code": "SYN-Q", "title": "Synthetic"},
    )
    assert form.status_code == 201
    version = client.post(
        f"/api/v1/clinical-support/questionnaires/{form.json()['id']}/versions",
        headers=doctor,
        json={"version_number": 1, "items_json": '[{"code":"Q1","type":"number","required":true,"min":0,"max":10}]'},
    )
    assert version.status_code == 201
    assigned = client.post(
        "/api/v1/clinical-support/visit-forms",
        headers=doctor,
        json={"study_id": study_id, "visit_code": "BASE", "definition_id": form.json()["id"]},
    )
    assert assigned.status_code == 201
    response = client.post(
        "/api/v1/clinical-support/questionnaire-responses",
        headers=doctor,
        json={"version_id": version.json()["id"], "visit_id": visit_id},
    )
    assert response.status_code == 201
    saved = client.post(
        f"/api/v1/clinical-support/questionnaire-responses/{response.json()['id']}/items",
        headers=doctor,
        json={"item_code": "Q1", "value_json": "4"},
    )
    assert saved.status_code == 200
    done = client.post(
        f"/api/v1/clinical-support/questionnaire-responses/{response.json()['id']}/finalize",
        headers=doctor,
    )
    assert done.status_code == 200
    assert done.json()["status"] == "final"
    template = client.get("/api/v1/clinical-support/templates/medi-des-001", headers=doctor)
    assert template.status_code == 200
    assert template.json()["status"] == "BLOCKED_PENDING_SOURCE"
    assert template.json()["visit_windows"] is None


def test_quality_rule_does_not_change_observation() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    event.listen(engine, "connect", lambda dbapi, _rec: dbapi.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine, tables=_TABLES)
    db = Session(engine)
    study = create_study(db, code="Q", name="Q", study_kind="prospective")
    site = add_site(db, study_id=study.id, site_code="S", name="S", actor_user_id="doc-a")
    add_site_member(db, site_id=site.id, user_id="doc-a", role="investigator", actor_user_id="doc-a")
    subject = enroll_subject(db, study_id=study.id, site_id=site.id, subject_code="S1", actor_user_id="doc-a")
    visit = open_visit(db, subject_id=subject.id, visit_code="BASE", occurred_on=date(2026, 3, 1), actor_user_id="doc-a")
    draft = create_draft_observation(
        db, visit_id=visit.id, code="TBUT", value_number=4, unit="s",
        recorded_by="doc-a", actor_user_id="doc-a",
    )
    final = finalize_observation(db, draft.id, actor_user_id="doc-a")
    before = (float(final.value_number), final.row_hash)
    add_quality_rule(
        db, study_id=study.id, code="RANGE", version_number=1, severity="error",
        logic_json='{"kind":"numeric_range","code":"TBUT","min":0,"max":3}',
    )
    found = run_quality_rules(db, study_id=study.id, actor_user_id="doc-a")
    db.refresh(final)
    assert len(found) == 1
    assert (float(final.value_number), final.row_hash) == before
    review_finding(db, found[0].id, actor_user_id="doc-a", reason="확인")
    db.refresh(final)
    assert (float(final.value_number), final.row_hash) == before
    again = run_quality_rules(db, study_id=study.id, actor_user_id="doc-a")
    assert again == []
    assert db.scalar(select(DataQualityFinding).where(DataQualityFinding.id == found[0].id)).status == "reviewed"
    db.close()
