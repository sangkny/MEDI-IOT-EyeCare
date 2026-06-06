"""AMD CNN 결과 — Ontology SEMANTIC 검증."""
from __future__ import annotations

from typing import Any

from ontology.base import ValidationResult, ValidatorType
from ontology.validator import OntologyValidator

from services.amd_cnn import AMDPrediction


def build_amd_ontology_payload(
    pred: AMDPrediction,
    *,
    model_used: str = "",
    icd10_code: str = "",
    referral_urgency: str = "none",
    eye: str | None = None,
) -> dict[str, Any]:
    laterality = None
    if eye:
        e = eye.strip().lower()
        if e in ("right", "od", "r"):
            laterality = "OD"
        elif e in ("left", "os", "l"):
            laterality = "OS"
    return {
        "task": "amd",
        "amd_grade": pred.amd_grade,
        "grade_label": pred.grade_label,
        "label": pred.label,
        "probability": pred.probability,
        "confidence": pred.confidence,
        "risk_level": pred.risk_level,
        "severity": pred.grade_label,
        "drusen_type": pred.drusen_type,
        "drusen_detected": pred.drusen_type != "none",
        "vision_impact": pred.vision_impact,
        "icd10_code": icd10_code or pred.icd10_code,
        "referral_urgency": referral_urgency or pred.referral_urgency,
        "model_used": model_used,
        "laterality": laterality,
        "finding_side": laterality,
    }


async def validate_amd_ontology(payload: dict[str, Any]) -> ValidationResult:
    validator = OntologyValidator.for_medical()
    return await validator.validate_partial(payload, [ValidatorType.SEMANTIC])
