"""안저·통합 진단 — 4-에이전트 결정 분기 (legacy Ontology 유지)."""
from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger("services.diagnosis_pipeline")

_pipeline: Any = None


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        from agents.feature_flags import AgentFeatureFlags
        from agents.pipeline import AgentPipeline

        _pipeline = (AgentFeatureFlags, AgentPipeline)
    return _pipeline


async def apply_four_agent_decision(
    *,
    dr_grade: int,
    confidence: float,
    icd10_code: str,
    patient_explanation: str,
    clinical_summary: str = "",
    ontology_passed_legacy: bool,
    patient_id: str | None,
) -> tuple[bool, dict, str]:
    """
    four_agent 활성 시 run_decision으로 ontology_passed·audit_trail 산출.
    비활성 시 legacy 값 유지.
    """
    AgentFeatureFlags, AgentPipeline = _get_pipeline()
    req_id = patient_id or "medi-anonymous"
    if not AgentFeatureFlags.is_four_agent_enabled(req_id):
        return (
            ontology_passed_legacy,
            {"mode": "legacy", "ontology_passed_legacy": ontology_passed_legacy},
            "legacy",
        )

    artifact = {
        "dr_grade": dr_grade,
        "confidence": confidence,
        "icd10": icd10_code,
        "icd10_code": icd10_code,
        "explanation": patient_explanation,
        "clinical_summary": clinical_summary,
    }
    pipe = AgentPipeline(domain="medical", task_id=f"medi-{req_id[:12]}")
    try:
        pr = await pipe.run_decision(artifact, "medical", request_id=req_id)
    except Exception as exc:
        log.warning("four_agent decision failed, fallback legacy: %s", exc)
        return (
            ontology_passed_legacy,
            {"mode": "legacy", "error": str(exc)[:200]},
            "legacy",
        )

    decision = pr.decision.decision
    ontology_passed = decision != "REJECT"
    audit = dict(pr.audit_trail or {})
    audit.setdefault("mode", pr.mode)
    audit.setdefault("decision", decision)
    return ontology_passed, audit, pr.mode


def four_agent_mock_for_lab() -> bool:
    return os.getenv("AGENT_FOUR_AGENT_MOCK", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
