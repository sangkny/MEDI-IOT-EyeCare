"""Glaucoma CNN 결과 — Ontology SEMANTIC 검증."""
from __future__ import annotations

from typing import Any

from ontology.base import ValidationResult, ValidatorType
from ontology.validator import OntologyValidator

from services.glaucoma_cnn import GlaucomaPrediction


def build_glaucoma_ontology_payload(
    pred: GlaucomaPrediction,
    *,
    model_used: str = "",
    icd10_code: str = "",
    referral_urgency: str = "none",
    eye: str | None = None,
    cup_disc_ratio: dict[str, Any] | None = None,
) -> dict[str, Any]:
    laterality = None
    if eye:
        e = eye.strip().lower()
        if e in ("right", "od", "r"):
            laterality = "OD"
        elif e in ("left", "os", "l"):
            laterality = "OS"
    return {
        "task": "glaucoma",
        "glaucoma_grade": pred.glaucoma_grade,
        "grade_label": pred.grade_label,
        "label": pred.label,
        "probability": pred.probability,
        "confidence": pred.confidence,
        "risk_level": pred.risk_level,
        "severity": pred.grade_label,
        "icd10_code": icd10_code,
        "referral_urgency": referral_urgency,
        "model_used": model_used,
        "laterality": laterality,
        "finding_side": laterality,
        "cup_disc_ratio": cup_disc_ratio,
    }


async def validate_glaucoma_ontology(payload: dict[str, Any]) -> ValidationResult:
    """SEMANTIC only — DR structural 필드(patient_id 등) 요구 없음."""
    validator = OntologyValidator.for_medical()
    return await validator.validate_partial(payload, [ValidatorType.SEMANTIC])
