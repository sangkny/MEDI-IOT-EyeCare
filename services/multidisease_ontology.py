"""다질환 스크리닝 — Ontology MULTI-SEM 검증."""
from __future__ import annotations

from typing import Any

from ontology.base import Severity, ValidationResult, ValidatorType
from ontology.validator import OntologyValidator

from schemas.integrated_diagnosis import ScreeningResult
from services.multidisease_cnn import MultidiseasePrediction, get_multidisease_threshold


def build_multidisease_ontology_payload(
    pred: MultidiseasePrediction,
    *,
    screening: ScreeningResult,
    model_used: str = "",
    threshold: float | None = None,
    eye: str | None = None,
) -> dict[str, Any]:
    laterality = None
    if eye:
        e = eye.strip().lower()
        if e in ("right", "od", "r"):
            laterality = "OD"
        elif e in ("left", "os", "l"):
            laterality = "OS"
    th = threshold if threshold is not None else get_multidisease_threshold()
    return {
        "task": "multidisease",
        "probabilities": dict(pred.probabilities),
        "findings": [f.model_dump() for f in screening.findings],
        "urgent_diseases": list(screening.urgent_diseases),
        "normal": screening.normal,
        "referral_urgency": screening.referral_urgency,
        "threshold": th,
        "model_used": model_used,
        "laterality": laterality,
        "finding_side": laterality,
    }


async def validate_multidisease_ontology(payload: dict[str, Any]) -> ValidationResult:
    validator = OntologyValidator.for_medical()
    return await validator.validate_partial(payload, [ValidatorType.SEMANTIC])


async def apply_multidisease_ontology(
    payload: dict[str, Any],
    draft: ScreeningResult,
) -> ScreeningResult:
    result = await validate_multidisease_ontology(payload)
    recs = list(draft.recommendations)
    urgency = draft.referral_urgency

    for err in result.errors:
        if err.code == "MULTI-SEM-001" and err.severity == Severity.ERROR:
            urgency = "immediate"

    for warn in result.warnings:
        if warn.code == "MULTI-SEM-002" and warn.message not in recs:
            recs.append(warn.message)

    probs = payload.get("probabilities") or {}
    for code in ("crvo", "aion"):
        if float(probs.get(code, 0)) > 0.5:
            urgency = "immediate"

    return draft.model_copy(
        update={
            "referral_urgency": urgency,
            "recommendations": recs,
            "urgent_referral": urgency == "immediate" or bool(draft.urgent_diseases),
        }
    )
