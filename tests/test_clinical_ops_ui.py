"""Phase 014 Clinical Operations UI — 세션·감사·페이지·권한."""
from __future__ import annotations

import asyncio
import importlib.util
from datetime import timedelta
from pathlib import Path

import pytest
from auth.jwt_handler import create_access_token
from fastapi import FastAPI
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from database import Base, get_db
from models.clinical import ClinicalStudy
from models.clinical_support import (
    AuditEventChain,
    ClinicalAuditEvent,
    ClinicalObservation,
    StudySite,
    StudySiteMember,
    StudySubject,
    StudyVisit,
)
from models.medical import Diagnosis, EyeExam, Patient
from services.clinical_records import _audit, create_study, add_site, add_site_member, enroll_subject
from tests.pg_test_isolation import unique_study_code

_ROOT = Path(__file__).resolve().parents[1]
_TABLES = [
    Patient.__table__,
    EyeExam.__table__,
    Diagnosis.__table__,
    ClinicalStudy.__table__,
    StudySite.__table__,
    StudySiteMember.__table__,
    StudySubject.__table__,
    StudyVisit.__table__,
    ClinicalObservation.__table__,
    ClinicalAuditEvent.__table__,
    AuditEventChain.__table__,
]

pytestmark = pytest.mark.unit


def _load_ops_module():
    spec = importlib.util.spec_from_file_location(
        "clinical_ops_api", _ROOT / "api" / "clinical_ops.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _seed(session: Session) -> tuple[ClinicalStudy, StudySite, StudySubject]:
    code = unique_study_code("DES")
    study = create_study(session, code=code, name="Synthetic DES", actor_user_id="doc-a")
    site = add_site(session, study_id=study.id, site_code="S01", name="Site 1", actor_user_id="doc-a")
    add_site_member(session, site_id=site.id, user_id="doc-a", role="investigator", actor_user_id="doc-a")
    add_site_member(session, site_id=site.id, user_id="dm-a", role="data_manager", actor_user_id="doc-a")
    subject = enroll_subject(
        session, study_id=study.id, site_id=site.id, subject_code="SYN-01", actor_user_id="doc-a",
    )
    _audit(
        session,
        study_id=study.id,
        actor_user_id="doc-a",
        action="subject_enroll",
        target_type="subject",
        target_id=subject.id,
        payload={"subject_code": "SYN-01"},
        site_id=site.id,
        link_chain=True,
        actor_role="investigator",
        correlation_id="corr-014",
    )
    session.flush()
    return study, site, subject


@pytest.fixture()
def ops_client():
    module = _load_ops_module()
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    event.listen(engine.sync_engine, "connect", lambda dbapi, _rec: dbapi.execute("PRAGMA foreign_keys=ON"))

    async def _prepare():
        async with engine.begin() as conn:
            await conn.run_sync(lambda sync: Base.metadata.create_all(sync, tables=_TABLES))

        def _fill(sync):
            session = Session(bind=sync)
            study, site, subject = _seed(session)
            ids = (study.id, site.id, subject.id, study.code)
            session.close()
            return ids

        async with engine.begin() as conn:
            return await conn.run_sync(_fill)

    study_id, site_id, subject_id, study_code = asyncio.run(_prepare())
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
    app.include_router(module.page_router)
    app.include_router(module.router, prefix="/api/v1/clinical-support")
    app.dependency_overrides[get_db] = _db
    client = TestClient(app)
    try:
        yield client, study_id, site_id, subject_id, study_code
    finally:
        client.close()
        asyncio.run(engine.dispose())


def test_clinical_ops_page_served(ops_client) -> None:
    client, *_ = ops_client
    page = client.get("/clinical-ops")
    assert page.status_code == 200
    assert "Clinical Operations" in page.text
    assert "ops-session.js" in page.text
    css = client.get("/clinical-ops/ops.css")
    assert css.status_code == 200
    js = client.get("/clinical-ops/ops-session.js")
    assert js.status_code == 200
    assert "localStorage.setItem" not in js.text
    assert "localStorage.getItem" not in js.text


def test_ops_session_requires_auth(ops_client) -> None:
    client, study_id, *_ = ops_client
    assert client.get("/api/v1/clinical-support/ops/session").status_code == 401
    doctor = {"Authorization": f"Bearer {create_access_token(subject='doc-a', role='doctor')}"}
    ok = client.get("/api/v1/clinical-support/ops/session", headers=doctor)
    assert ok.status_code == 200
    body = ok.json()
    assert body["user_id"] == "doc-a"
    assert body["role"] == "doctor"
    assert "audit" in body["nav"]
    assert any(row["id"] == study_id for row in body["studies"])
    outsider = {"Authorization": f"Bearer {create_access_token(subject='other', role='doctor')}"}
    empty = client.get("/api/v1/clinical-support/ops/session", headers=outsider)
    assert empty.status_code == 200
    assert empty.json()["studies"] == []


def test_ops_audits_authorized_and_integrity_labels(ops_client) -> None:
    client, study_id, site_id, subject_id, _ = ops_client
    doctor = {"Authorization": f"Bearer {create_access_token(subject='doc-a', role='doctor')}"}
    denied = client.get("/api/v1/clinical-support/ops/audits", params={"study_id": study_id})
    assert denied.status_code == 401
    outsider = {"Authorization": f"Bearer {create_access_token(subject='other', role='doctor')}"}
    forbidden = client.get(
        "/api/v1/clinical-support/ops/audits",
        params={"study_id": study_id},
        headers=outsider,
    )
    assert forbidden.status_code == 403
    rows = client.get(
        "/api/v1/clinical-support/ops/audits",
        params={"study_id": study_id, "site_id": site_id, "action": "subject"},
        headers=doctor,
    )
    assert rows.status_code == 200
    payload = rows.json()
    assert payload
    event = payload[0]
    assert event["integrity_status"] in {
        "HASH_CHAINED", "EVENT_HASH_ONLY", "LEGACY_HASH_ONLY", "HASH_CHAINED_PAYLOAD_MISMATCH",
    }
    assert "payload_json" not in event
    assert event.get("correlation_id")
    # blanket crypto claim must not appear in API
    assert "cryptographically verified" not in str(payload).lower()


def test_expired_token_rejected(ops_client) -> None:
    client, study_id, *_ = ops_client
    try:
        token = create_access_token(
            subject="doc-a", role="doctor", expires_delta=timedelta(seconds=-30),
        )
    except TypeError:
        pytest.skip("create_access_token expires_delta not supported")
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/v1/clinical-support/ops/session", headers=headers)
    assert response.status_code == 401


def test_path_traversal_blocked(ops_client) -> None:
    client, *_ = ops_client
    assert client.get("/clinical-ops/../main.py").status_code in {400, 404}
