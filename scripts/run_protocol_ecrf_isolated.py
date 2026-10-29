"""합성 SQLite로 계획서 eCRF 화면만 띄운다. 전체 앱이나 운영 데이터베이스를 열지 않는다."""
from __future__ import annotations

import os
import sys
import types
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SHARED = Path(r"C:\Tools\downloads\phase005-inspect\shared-libraries")
sys.path.insert(0, str(_SHARED))
sys.path.insert(0, str(_ROOT))
if "models" not in sys.modules:
    _models = types.ModuleType("models")
    _models.__path__ = [str(_ROOT / "models")]
    sys.modules["models"] = _models

import uvicorn
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import create_engine
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
    ProtocolDocument,
    StudySite,
    StudySiteMember,
    StudySubject,
    StudyVisit,
    VisitWindow,
)
from models.medical import Diagnosis, EyeExam, Patient
from services.clinical_records import add_site, add_site_member, create_study, enroll_subject, open_visit
from services.protocol_ecrf import (
    activate_schema,
    generate_draft,
    register_protocol,
    render_schema,
    simulate_approval,
)

print("BOOT", flush=True)
TOKEN = "synthetic-ecrf-demo"
SHA110 = "9e24fcedbd869e4e2b88d8b33e32acf617d4fd541199c78cd4c75d6444e2ac44"
engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TABLES = [
    Patient.__table__, EyeExam.__table__, Diagnosis.__table__, ClinicalStudy.__table__,
    StudySite.__table__, StudySiteMember.__table__, VisitWindow.__table__,
    StudySubject.__table__, StudyVisit.__table__, ClinicalAuditEvent.__table__,
    DataLockState.__table__, ProtocolDocument.__table__, EcrfSchemaVersion.__table__,
    EcrfEntry.__table__, AuditEventChain.__table__,
]
Base.metadata.create_all(engine, tables=TABLES)
with Session(engine) as session:
    study = create_study(session, code="SYN-ECRF", name="synthetic")
    site = add_site(session, study_id=study.id, site_code="S1", name="Site", actor_user_id="doc")
    add_site_member(session, site_id=site.id, user_id="doc", role="doctor", actor_user_id="doc")
    subject = enroll_subject(
        session, study_id=study.id, site_id=site.id, subject_code="SYN-01", actor_user_id="doc",
    )
    open_visit(session, subject_id=subject.id, visit_code="V1", occurred_on=date(2026, 3, 2), actor_user_id="doc")
    document = register_protocol(
        session, study_id=study.id, site_id=site.id, actor_user_id="doc", actor_role="doctor",
        version_label="1.10", source_sha256=SHA110, document_date="2026-07-01",
        source_present=True, source_reference="local protocol pdf",
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
    session.commit()
    STUDY_ID = study.id
    SITE_ID = site.id
    SCHEMA_ID = schema.id

app = FastAPI()
PAGE = _ROOT / "static" / "protocol-ecrf" / "index.html"


@app.get("/protocol-ecrf")
def page():
    return FileResponse(PAGE, media_type="text/html; charset=utf-8")


@app.get("/api/v1/clinical-support/studies/{study_id}/ecrf-schemas/{schema_id}")
def read_schema(study_id: str, schema_id: str, site_id: str, authorization: str | None = Header(default=None)):
    if authorization != f"Bearer {TOKEN}":
        raise HTTPException(status_code=401, detail="인증이 필요합니다.")
    if study_id != STUDY_ID or site_id != SITE_ID or schema_id != SCHEMA_ID:
        raise HTTPException(status_code=403, detail="사이트 구성원이 아닙니다.")
    with Session(engine) as session:
        return render_schema(session.get(EcrfSchemaVersion, schema_id))


if __name__ == "__main__":
    port = int(os.environ.get("ECRF_PORT", "8772"))
    print(f"ECRF READY study={STUDY_ID} site={SITE_ID} schema={SCHEMA_ID} token={TOKEN} port={port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
