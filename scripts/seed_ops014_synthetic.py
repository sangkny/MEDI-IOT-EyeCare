"""Synthetic DES/AMD seed for Phase 014 browser E2E. No real clinical data."""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from services.amd_protocol_catalog import SOURCE_SHA256 as AMD_SHA, install_amd_catalog
from services.clinical_lock import apply_lock, request_lock
from services.clinical_quality import run_quality_rules
from services.clinical_queries import create_query, resolve_query, respond_to_query
from services.clinical_readiness import approve_protocol_definition, register_protocol_definition
from services.clinical_records import (
    add_site,
    add_site_member,
    create_draft_observation,
    create_study,
    enroll_subject,
    finalize_observation,
    open_visit,
)
from services.protocol_ecrf import generate_draft, register_protocol
from services.questionnaire_engine import generate_osdi_draft

_DES_SHA = "9e24fcedbd869e4e2b88d8b33e32acf617d4fd541199c78cd4c75d6444e2ac44"
_OUT = Path(os.environ.get("OPS014_SEED_MANIFEST", "docs/ops014-seed-manifest.json"))


def _requirements() -> dict:
    return {
        "required_observations": [{"code": "TBUT"}, {"code": "SCHIRMER"}],
        "blocking_query_severities": ["error", "critical"],
        "blocking_finding_severities": ["error", "critical"],
    }


def seed(session: Session) -> dict:
    install_amd_catalog()
    session.info["link_audit_chain"] = True
    suffix = uuid.uuid4().hex[:6].upper()

    # --- DES ---
    des = create_study(
        session, code=f"MEDI-DES-001-{suffix}", name="MEDI-DES-001 synthetic",
        study_kind="prospective", protocol_version="1.10",
    )
    des_site = add_site(session, study_id=des.id, site_code="DES-S1", name="DES Site", actor_user_id="doctor")
    add_site_member(session, site_id=des_site.id, user_id="doctor", role="investigator", actor_user_id="doctor")
    add_site_member(session, site_id=des_site.id, user_id="admin", role="data_manager", actor_user_id="doctor")
    des_subject = enroll_subject(
        session, study_id=des.id, site_id=des_site.id, subject_code="DES-SYN-01", actor_user_id="doctor",
    )
    des_visit = open_visit(
        session, subject_id=des_subject.id, visit_code="V2", occurred_on=date(2026, 8, 1), actor_user_id="doctor",
    )
    des_doc = register_protocol(
        session, study_id=des.id, site_id=des_site.id, actor_user_id="doctor", actor_role="doctor",
        version_label="1.10", source_sha256=_DES_SHA, document_date="2026-07-01",
        source_present=True, source_reference="synthetic des protocol hash only",
        protocol_identifier="MEDI-DES-001",
    )
    des_schema = generate_draft(
        session, study_id=des.id, site_id=des_site.id, actor_user_id="doctor", actor_role="doctor",
        document_id=des_doc.id,
    )
    osdi = generate_osdi_draft(
        session, study_id=des.id, site_id=des_site.id, actor_user_id="doctor", actor_role="doctor",
        document_id=des_doc.id,
    )
    tbut_draft = create_draft_observation(
        session, visit_id=des_visit.id, code="TBUT", laterality="OD", value_number=6.5, unit="s",
        recorded_by="doctor", actor_user_id="doctor",
    )
    tbut = finalize_observation(session, tbut_draft.id, actor_user_id="doctor")
    schirmer_draft = create_draft_observation(
        session, visit_id=des_visit.id, code="SCHIRMER", laterality="OD", value_number=8.0, unit="mm",
        recorded_by="doctor", actor_user_id="doctor",
    )
    schirmer = finalize_observation(session, schirmer_draft.id, actor_user_id="doctor")
    proto = register_protocol_definition(
        session, study_id=des.id, actor_user_id="admin", requirements=_requirements(),
    )
    approve_protocol_definition(session, proto.id, actor_user_id="admin")
    run_quality_rules(session, study_id=des.id, actor_user_id="doctor")
    # Query history on subject (not on Schirmer lock target) so readiness stays COMPLETE.
    des_query = create_query(
        session, study_id=des.id, actor_user_id="doctor", category="manual", severity="medium",
        description="Synthetic DES query for ops014", subject_id=des_subject.id,
    )
    respond_to_query(session, des_query.id, actor_user_id="doctor", body="synthetic seed response")
    resolve_query(session, des_query.id, actor_user_id="doctor", reason="ops014 seed resolve")
    # Lock target: Schirmer. Seed leaves READY_FOR_REVIEW; browser applies LOCKED.
    request_lock(
        session, study_id=des.id, target_type="observation", target_id=schirmer.id,
        actor_user_id="admin", reason="ops014 seed readiness",
    )

    # --- AMD DRAFT ---
    amd = create_study(
        session, code=f"MEDI-AMD-001-{suffix}", name="MEDI-AMD-001 synthetic DRAFT",
        study_kind="prospective", protocol_version="0.1",
    )
    amd_site = add_site(session, study_id=amd.id, site_code="AMD-S1", name="AMD Site", actor_user_id="doctor")
    add_site_member(session, site_id=amd_site.id, user_id="doctor", role="investigator", actor_user_id="doctor")
    add_site_member(session, site_id=amd_site.id, user_id="admin", role="data_manager", actor_user_id="doctor")
    # outsider site for cross-site denial (doctor NOT a member)
    amd_other = add_site(session, study_id=amd.id, site_code="AMD-S2", name="AMD Other", actor_user_id="doctor")
    add_site_member(session, site_id=amd_other.id, user_id="admin", role="data_manager", actor_user_id="doctor")
    amd_subject = enroll_subject(
        session, study_id=amd.id, site_id=amd_site.id, subject_code="AMD-SYN-01", actor_user_id="doctor",
    )
    amd_visit = open_visit(
        session, subject_id=amd_subject.id, visit_code="V2", occurred_on=date(2026, 8, 2), actor_user_id="doctor",
    )
    amd_doc = register_protocol(
        session, study_id=amd.id, site_id=amd_site.id, actor_user_id="doctor", actor_role="doctor",
        version_label="0.1", source_sha256=AMD_SHA, document_date="2026-07-31",
        source_present=True, source_reference="synthetic amd draft hash only",
        protocol_identifier="MEDI-AMD-001",
    )
    amd_schema = generate_draft(
        session, study_id=amd.id, site_id=amd_site.id, actor_user_id="doctor", actor_role="doctor",
        document_id=amd_doc.id,
    )
    bcva_draft = create_draft_observation(
        session, visit_id=amd_visit.id, code="BCVA", laterality="OD", value_number=0.8, unit="logMAR",
        recorded_by="doctor", actor_user_id="doctor",
    )
    bcva = finalize_observation(session, bcva_draft.id, actor_user_id="doctor")
    oct_draft = create_draft_observation(
        session, visit_id=amd_visit.id, code="OCT_DRUSEN", laterality="OD", value_number=42.0, unit="um",
        recorded_by="doctor", actor_user_id="doctor",
    )
    oct = finalize_observation(session, oct_draft.id, actor_user_id="doctor")
    eye_draft = create_draft_observation(
        session, visit_id=amd_visit.id, code="STUDY_EYE", laterality="OD", value_text="OD", unit="code",
        recorded_by="doctor", actor_user_id="doctor",
    )
    study_eye = finalize_observation(session, eye_draft.id, actor_user_id="doctor")

    session.commit()
    amd_body = json.loads(amd_schema.definition_json)
    des_body = json.loads(des_schema.definition_json)
    return {
        "suffix": suffix,
        "des": {
            "study_id": des.id,
            "study_code": des.code,
            "site_id": des_site.id,
            "subject_id": des_subject.id,
            "visit_id": des_visit.id,
            "schema_id": des_schema.id,
            "osdi_version_id": osdi["version_id"],
            "tbut_observation_id": tbut.id,
            "schirmer_observation_id": schirmer.id,
            "query_id": des_query.id,
            "has_osdi_form": any(f["form_code"] == "OSDI" for f in des_body.get("forms", [])),
            "forms": [f["form_code"] for f in des_body.get("forms", [])],
        },
        "amd": {
            "study_id": amd.id,
            "study_code": amd.code,
            "site_id": amd_site.id,
            "other_site_id": amd_other.id,
            "subject_id": amd_subject.id,
            "visit_id": amd_visit.id,
            "schema_id": amd_schema.id,
            "bcva_observation_id": bcva.id,
            "oct_observation_id": oct.id,
            "study_eye_observation_id": study_eye.id,
            "has_osdi_form": any(f["form_code"] == "OSDI" for f in amd_body.get("forms", [])),
            "unresolved": amd_body.get("unresolved", []),
            "rules_active": amd_body.get("rules_active"),
            "forms": [f["form_code"] for f in amd_body.get("forms", [])],
        },
        "notes": {
            "amd_status": "DRAFT",
            "osdi_on_amd": False,
            "synthetic_only": True,
        },
    }


def main() -> int:
    url = os.environ.get("EYECARE_PG_URL") or os.environ.get("DATABASE_URL")
    if not url or not url.startswith("postgresql"):
        print("EYECARE_PG_URL required", file=sys.stderr)
        return 2
    if url.startswith("postgresql+asyncpg://"):
        url = "postgresql://" + url[len("postgresql+asyncpg://"):]
    engine = create_engine(url)
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as session:
        manifest = seed(session)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("SEEDED", _OUT)
    print(json.dumps({"des": manifest["des"]["study_code"], "amd": manifest["amd"]["study_code"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
