"""SVG-Analyzer용 읽기 전용 아키텍처 증거.

정식 계약 식별자는 SVG-Analyzer ADAPTER_SCHEMA 와 같다.
예전 초안 식별자 eyecare-architecture-evidence/v1 은 호환되지 않으며
내보내기에서 쓰지 않는다. 환자값·토큰·배정·PDF 본문은 넣지 않는다.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Canonical identifier from SVG-Analyzer svg_analyzer/architecture_review.py
CANONICAL_SCHEMA = "eyecare-architecture-evidence/1"
LEGACY_DRAFT_SCHEMA = "eyecare-architecture-evidence/v1"
SCHEMA_COMPATIBILITY = {
    LEGACY_DRAFT_SCHEMA: {
        "status": "REJECTED",
        "maps_to": CANONICAL_SCHEMA,
        "reason": "SVG-Analyzer load_evidence_contract accepts only /1",
    },
    CANONICAL_SCHEMA: {
        "status": "CANONICAL",
        "maps_to": CANONICAL_SCHEMA,
        "reason": "ADAPTER_SCHEMA",
    },
}
TOOL_VERSION = "012b.1"
_ROOT = Path(__file__).resolve().parents[1]

# module_id, paths, owner, critical, interfaces, db_owns, audit_covered, test_paths
MODULES = (
    ("protocol_registry", ["services/protocol_ecrf.py"], "clinical-platform", True,
     ["http:/api/v1/clinical-support/studies/{id}/protocol-documents"], ["protocol_documents"], True,
     ["tests/test_protocol_ecrf.py"]),
    ("protocol_extraction", ["services/clinical_protocol_rules.py"], "clinical-platform", True,
     [], [], True, ["tests/test_clinical_import.py"]),
    ("amendment_engine", ["services/protocol_ecrf.py"], "clinical-platform", True,
     ["http:/api/v1/clinical-support/studies/{id}/ecrf-amendments"], [], True,
     ["tests/test_protocol_ecrf.py"]),
    ("ecrf_schema", ["services/protocol_ecrf.py", "models/clinical_support.py"], "clinical-platform", True,
     ["http:/api/v1/clinical-support/studies/{id}/ecrf-schemas/{id}"],
     ["ecrf_schema_versions", "ecrf_entries"], True, ["tests/test_protocol_ecrf.py"]),
    ("ecrf_renderer", ["static/protocol-ecrf/index.html", "api/protocol_ecrf.py"], "clinical-platform", False,
     ["http:/protocol-ecrf"], [], False, ["tests/test_protocol_ecrf.py"]),
    ("questionnaire_definition", ["services/questionnaire_engine.py"], "clinical-platform", True,
     ["http:/api/v1/clinical-support/studies/{id}/questionnaire-drafts"],
     ["questionnaire_definitions", "questionnaire_versions"], True,
     ["tests/test_questionnaire_engine.py"]),
    ("questionnaire_response", ["services/clinical_records.py", "services/questionnaire_engine.py"],
     "clinical-platform", True,
     ["http:/api/v1/clinical-support/questionnaire-engine/responses"],
     ["questionnaire_responses", "questionnaire_response_items"], True,
     ["tests/test_questionnaire_engine.py"]),
    ("questionnaire_scoring", ["services/questionnaire_engine.py"], "clinical-platform", True,
     ["http:/api/v1/clinical-support/questionnaire-engine/responses/{id}/score"],
     ["questionnaire_score_results"], True, ["tests/test_questionnaire_engine.py"]),
    ("questionnaire_analytics", ["services/questionnaire_engine.py"], "clinical-platform", False,
     ["http:/api/v1/clinical-support/studies/{id}/questionnaire-stats"], [], True,
     ["tests/test_questionnaire_engine.py"]),
    ("clinical_records", ["services/clinical_records.py"], "clinical-platform", True,
     [], ["clinical_observations"], True, ["tests/test_observation_lifecycle.py"]),
    ("data_quality", ["services/clinical_quality.py"], "clinical-platform", True,
     [], ["data_quality_findings"], True, ["tests/test_clinical_query_quality.py"]),
    ("clinical_query", ["services/clinical_queries.py"], "clinical-platform", True,
     [], ["clinical_queries"], True, ["tests/test_clinical_query_quality.py"]),
    ("audit_trail", ["services/clinical_records.py", "models/clinical_support.py"], "clinical-platform", True,
     ["http:/api/v1/clinical-support/architecture-evidence"],
     ["clinical_audit_events", "audit_event_chains"], True,
     ["tests/test_protocol_ecrf.py", "tests/test_questionnaire_engine.py"]),
    ("dashboard", ["services/clinical_case_dashboard.py", "api/clinical_dashboard.py"],
     "clinical-platform", False, ["http:/clinical-dashboard"], [], True,
     ["tests/test_clinical_case_dashboard.py"]),
    ("import_reconciliation", ["services/clinical_import.py"], "clinical-platform", True,
     [], ["import_batches"], True, ["tests/test_clinical_import.py"]),
    ("analyzer_integration", ["services/architecture_evidence.py", "services/improvement_loop.py"],
     "clinical-platform", True,
     ["http:/api/v1/clinical-support/architecture-evidence",
      "http:/api/v1/clinical-support/improvement-findings"],
     ["improvement_findings"], True, ["tests/test_questionnaire_engine.py"]),
    ("multi_protocol_catalogs", ["services/amd_protocol_catalog.py", "services/amd_stats_poc.py"],
     "clinical-platform", True,
     [], [], True,
     ["tests/test_multi_protocol_amd_013.py"]),
    ("alembic", ["alembic/versions"], "clinical-platform", True, [], [], True,
     ["tests/test_clinical_import.py", "tests/test_clinical_data_lock.py"]),
)

EDGES = (
    ("protocol_registry", "protocol_extraction"),
    ("protocol_extraction", "ecrf_schema"),
    ("protocol_extraction", "questionnaire_definition"),
    ("ecrf_schema", "amendment_engine"),
    ("ecrf_schema", "ecrf_renderer"),
    ("questionnaire_definition", "questionnaire_response"),
    ("questionnaire_response", "questionnaire_scoring"),
    ("questionnaire_scoring", "questionnaire_analytics"),
    ("clinical_records", "audit_trail"),
    ("questionnaire_response", "audit_trail"),
    ("clinical_query", "audit_trail"),
    ("import_reconciliation", "data_quality"),
    ("analyzer_integration", "questionnaire_definition"),
    ("alembic", "ecrf_schema"),
    ("alembic", "questionnaire_scoring"),
)


def resolve_schema_id(requested: str | None = None) -> dict:
    """정식 식별자와 거절된 초안 식별자를 명시적으로 구분한다."""
    if requested is None:
        requested = CANONICAL_SCHEMA
    mapping = SCHEMA_COMPATIBILITY.get(requested)
    if mapping is None:
        return {
            "requested": requested,
            "status": "UNKNOWN",
            "maps_to": None,
            "accepted": False,
            "reason": "not listed in SCHEMA_COMPATIBILITY",
        }
    return {
        "requested": requested,
        "accepted": mapping["status"] == "CANONICAL",
        **mapping,
    }


def _commit_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=_ROOT, text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def build_architecture_evidence(*, test_results: dict | None = None) -> dict:
    modules = []
    for module_id, paths, owner, critical, interfaces, db_owns, audit_covered, test_paths in MODULES:
        modules.append({
            "module_id": module_id,
            "paths": list(paths),
            "owner": owner,
            "critical": critical,
            "interfaces": list(interfaces),
            "db_owns": list(db_owns),
            "audit_covered": audit_covered,
            "test_paths": list(test_paths),
        })
    migrations = sorted(path.name for path in (_ROOT / "alembic" / "versions").glob("*.py"))
    payload = {
        "schema": CANONICAL_SCHEMA,
        "modules": modules,
        "edges": [
            {"source": source, "target": target, "kind": "declared"}
            for source, target in EDGES
        ],
        # Optional EYECARE metadata. Analyzer ignores unknown top-level keys.
        "eyecare_meta": {
            "tool_version": TOOL_VERSION,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "repository_commit_sha": _commit_sha(),
            "schema_compatibility": SCHEMA_COMPATIBILITY,
            "migration_ancestry": migrations,
            "test_results": test_results or {},
            "audit_coverage": {
                "hash_chained": [
                    "protocol_registered",
                    "ecrf_generated",
                    "questionnaire_drafted",
                    "questionnaire_response_started",
                    "questionnaire_item_saved",
                    "questionnaire_response_finalized",
                    "questionnaire_scored",
                ],
                "event_only": ["clinical_query", "data_lock", "clinical_import"],
                "missing": ["electronic_signature", "data_export"],
            },
            "exclusions": [
                "patient_records",
                "credentials",
                "unblinded_allocation",
                "response_values",
                "protocol_pdf_bodies",
            ],
            "legacy_draft_schema": LEGACY_DRAFT_SCHEMA,
            "legacy_draft_status": "REJECTED",
        },
    }
    return payload


def validate_evidence(payload: dict) -> list[str]:
    errors = []
    schema = payload.get("schema")
    resolved = resolve_schema_id(schema if isinstance(schema, str) else None)
    if not resolved.get("accepted"):
        errors.append("schema")
    if not isinstance(payload.get("modules"), list) or not payload["modules"]:
        errors.append("modules")
    else:
        for item in payload["modules"]:
            for key in ("module_id", "paths", "owner", "critical", "interfaces", "db_owns",
                        "audit_covered", "test_paths"):
                if key not in item:
                    errors.append(f"module.{key}")
                    break
    if not isinstance(payload.get("edges"), list):
        errors.append("edges")
    else:
        for edge in payload["edges"]:
            if not {"source", "target", "kind"} <= set(edge):
                errors.append("edge.shape")
                break
    return sorted(set(errors))


def write_offline_evidence(path: Path | None = None, *, test_results: dict | None = None) -> Path:
    """오프라인 분석용 JSON. Git에 환자 데이터를 넣지 않는다."""
    target = path or (_ROOT / "docs" / "architecture-evidence.json")
    payload = build_architecture_evidence(test_results=test_results)
    errors = validate_evidence(payload)
    if errors:
        raise ValueError(f"evidence invalid: {errors}")
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target
