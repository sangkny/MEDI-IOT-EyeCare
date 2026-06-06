"""안저·통합 진단 — 4-에이전트 결정 분기 (legacy Ontology 유지)."""
from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger("services.diagnosis_pipeline")

_pipeline: Any = None

GLAUCOMA_UNCERTAIN_LOW = 0.45
GLAUCOMA_UNCERTAIN_HIGH = 0.55


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        from agents.feature_flags import AgentFeatureFlags
        from agents.pipeline import AgentPipeline

        _pipeline = (AgentFeatureFlags, AgentPipeline)
    return _pipeline


def _dr_decision_gate_min() -> float:
    try:
        return float(os.getenv("MEDI_CNN_DECISION_MIN_CONF", "0.80"))
    except ValueError:
        return 0.80


def _dr_decision_reject_max() -> float:
    try:
        return float(os.getenv("MEDI_CNN_DECISION_REJECT_MAX", "0.50"))
    except ValueError:
        return 0.50


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
    """Ontology legacy + DecisionGate + four_agent.

    - confidence >= gate_min (기본 0.80): APPROVE (four_agent 또는 legacy)
    - reject_max ~ gate_min (기본 0.50~0.80): REVISE (DR grade >= 1 포함)
    - confidence < reject_max and dr_grade == 0: REJECT
    """
    gate_min = _dr_decision_gate_min()
    reject_max = _dr_decision_reject_max()
    audit: dict[str, Any] = {
        "threshold": gate_min,
        "reject_max": reject_max,
        "confidence": confidence,
    }

    if confidence < reject_max and dr_grade == 0:
        audit.update(mode="gate", decision="REJECT", reason="below_reject_max")
        return False, audit, "gate"

    if confidence < gate_min:
        audit.update(mode="gate", decision="REVISE", reason="below_gate_min")
        return True, audit, "gate"

    AgentFeatureFlags, AgentPipeline = _get_pipeline()
    req_id = patient_id or "medi-anonymous"
    if not AgentFeatureFlags.is_four_agent_enabled(req_id):
        audit.update(
            mode="legacy",
            decision="APPROVE",
            ontology_passed_legacy=ontology_passed_legacy,
        )
        return ontology_passed_legacy, audit, "legacy"

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
        audit.update(mode="legacy", decision="APPROVE", error=str(exc)[:200])
        return ontology_passed_legacy, audit, "legacy"

    decision = pr.decision.decision
    audit = {**audit, **dict(pr.audit_trail or {})}
    audit.setdefault("mode", pr.mode)
    if decision == "REJECT" and confidence >= gate_min:
        decision = "REVISE"
        audit["decision_softened"] = True
    audit["decision"] = decision
    ontology_passed = decision != "REJECT"
    return ontology_passed, audit, pr.mode


def four_agent_mock_for_lab() -> bool:
    return os.getenv("AGENT_FOUR_AGENT_MOCK", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _glaucoma_decision_gate_min() -> float:
    try:
        return float(os.getenv("MEDI_GLAUCOMA_DECISION_MIN_CONF", "0.65"))
    except ValueError:
        return 0.65


def _ontology_issues_summary(validation: Any) -> list[str]:
    issues: list[str] = []
    for err in getattr(validation, "errors", []) or []:
        issues.append(f"{err.code}: {err.message}")
    return issues[:8]


async def apply_four_agent_glaucoma_decision(
    *,
    probability: float,
    confidence: float,
    label: str,
    glaucoma_grade: int,
    patient_id: str | None,
    ontology_payload: dict[str, Any] | None = None,
) -> tuple[bool, dict, str]:
    """Ontology(SEMANTIC) + DecisionGate(기본 0.65) + four_agent.

    - 0.45 ≤ probability ≤ 0.55: REJECT (불확실 구간)
    - gate_min 미만(기본 0.65): REVISE (ontology 통과 시 ontology_passed=True)
    - confidence ≥ gate_min: four_agent 또는 legacy APPROVE
    """
    from services.glaucoma_ontology import validate_glaucoma_ontology

    gate_min = _glaucoma_decision_gate_min()
    audit: dict[str, Any] = {
        "threshold": gate_min,
        "uncertain_band": [GLAUCOMA_UNCERTAIN_LOW, GLAUCOMA_UNCERTAIN_HIGH],
        "confidence": confidence,
        "probability": probability,
    }

    ont_passed = True
    if ontology_payload:
        validation = await validate_glaucoma_ontology(ontology_payload)
        ont_passed = validation.passed
        audit["ontology_passed"] = ont_passed
        audit["ontology_errors"] = _ontology_issues_summary(validation)
        audit["ontology_warnings"] = len(getattr(validation, "warnings", []) or [])

    if not ont_passed:
        audit.update(mode="ontology", decision="REJECT")
        return False, audit, "ontology"

    if GLAUCOMA_UNCERTAIN_LOW <= probability <= GLAUCOMA_UNCERTAIN_HIGH:
        audit.update(mode="gate", decision="REJECT", reason="uncertain_probability")
        return False, audit, "gate"

    if confidence < gate_min:
        audit.update(mode="gate", decision="REVISE", reason="below_gate_min")
        return True, audit, "gate"

    AgentFeatureFlags, AgentPipeline = _get_pipeline()
    req_id = patient_id or "medi-anonymous"
    if not AgentFeatureFlags.is_four_agent_enabled(req_id):
        audit.update(mode="legacy", decision="APPROVE")
        return True, audit, "legacy"

    artifact = {
        "task": "glaucoma",
        "condition": "open_angle_glaucoma" if label == "glaucoma" else "normal_fundus",
        "glaucoma_grade": glaucoma_grade,
        "confidence": confidence,
        "probability": probability,
        "icd10": "H40.1" if glaucoma_grade >= 1 else "H40.0",
        "icd10_code": "H40.1" if glaucoma_grade >= 1 else "H40.0",
        "explanation": f"Glaucoma CNN: {label} (p={probability:.3f})",
    }
    if ontology_payload:
        artifact.update(ontology_payload)

    pipe = AgentPipeline(domain="medical", task_id=f"medi-glaucoma-{req_id[:12]}")
    try:
        pr = await pipe.run_decision(artifact, "medical", request_id=req_id)
    except Exception as exc:
        log.warning("four_agent glaucoma decision failed, legacy approve: %s", exc)
        audit.update(mode="gate", decision="APPROVE", error=str(exc)[:200])
        return True, audit, "gate"

    decision = pr.decision.decision
    audit = {**audit, **dict(pr.audit_trail or {})}
    audit.setdefault("mode", pr.mode)
    if decision == "REJECT" and ont_passed and confidence >= gate_min:
        decision = "REVISE"
        audit["decision_softened"] = True
    audit["decision"] = decision
    return ont_passed, audit, pr.mode


AMD_UNCERTAIN_LOW = 0.45
AMD_UNCERTAIN_HIGH = 0.55


def _amd_decision_gate_min() -> float:
    try:
        return float(os.getenv("MEDI_AMD_DECISION_MIN_CONF", "0.65"))
    except ValueError:
        return 0.65


async def apply_four_agent_amd_decision(
    *,
    probability: float,
    confidence: float,
    label: str,
    amd_grade: int,
    patient_id: str | None,
    ontology_payload: dict[str, Any] | None = None,
) -> tuple[bool, dict, str]:
    """Ontology(SEMANTIC) + DecisionGate(기본 0.65) + four_agent."""
    from services.amd_ontology import validate_amd_ontology

    gate_min = _amd_decision_gate_min()
    audit: dict[str, Any] = {
        "threshold": gate_min,
        "uncertain_band": [AMD_UNCERTAIN_LOW, AMD_UNCERTAIN_HIGH],
        "confidence": confidence,
        "probability": probability,
    }

    ont_passed = True
    if ontology_payload:
        validation = await validate_amd_ontology(ontology_payload)
        ont_passed = validation.passed
        audit["ontology_passed"] = ont_passed
        audit["ontology_errors"] = _ontology_issues_summary(validation)
        audit["ontology_warnings"] = len(getattr(validation, "warnings", []) or [])

    if not ont_passed:
        audit.update(mode="ontology", decision="REJECT")
        return False, audit, "ontology"

    if AMD_UNCERTAIN_LOW <= probability <= AMD_UNCERTAIN_HIGH:
        audit.update(mode="gate", decision="REJECT", reason="uncertain_probability")
        return False, audit, "gate"

    if confidence < gate_min:
        audit.update(mode="gate", decision="REVISE", reason="below_gate_min")
        return True, audit, "gate"

    AgentFeatureFlags, AgentPipeline = _get_pipeline()
    req_id = patient_id or "medi-anonymous"
    if not AgentFeatureFlags.is_four_agent_enabled(req_id):
        audit.update(mode="legacy", decision="APPROVE")
        return True, audit, "legacy"

    artifact = {
        "task": "amd",
        "condition": "age_related_macular_degeneration" if label == "amd" else "normal_fundus",
        "amd_grade": amd_grade,
        "confidence": confidence,
        "probability": probability,
        "icd10": ontology_payload.get("icd10_code", "H35.31") if ontology_payload else "H35.31",
        "icd10_code": ontology_payload.get("icd10_code", "H35.31") if ontology_payload else "H35.31",
        "explanation": f"AMD CNN: {label} (p={probability:.3f})",
    }
    if ontology_payload:
        artifact.update(ontology_payload)

    pipe = AgentPipeline(domain="medical", task_id=f"medi-amd-{req_id[:12]}")
    try:
        pr = await pipe.run_decision(artifact, "medical", request_id=req_id)
    except Exception as exc:
        log.warning("four_agent amd decision failed, legacy approve: %s", exc)
        audit.update(mode="gate", decision="APPROVE", error=str(exc)[:200])
        return True, audit, "gate"

    decision = pr.decision.decision
    audit = {**audit, **dict(pr.audit_trail or {})}
    audit.setdefault("mode", pr.mode)
    if decision == "REJECT" and ont_passed and confidence >= gate_min:
        decision = "REVISE"
        audit["decision_softened"] = True
    audit["decision"] = decision
    return ont_passed, audit, pr.mode
