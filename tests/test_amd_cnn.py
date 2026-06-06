"""AMD CNN 매핑·온톨로지·API smoke."""
from __future__ import annotations

import pytest

from services.amd_cnn import (
    amd_prediction_from_probability,
    prediction_to_result,
    referral_from_risk,
    risk_level_from_probability,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "prob, risk, label, grade, drusen",
    [
        (0.1, "LOW", "normal", 0, "none"),
        (0.5, "MODERATE", "amd", 1, "soft"),
        (0.75, "HIGH", "amd", 2, "hard"),
        (0.9, "HIGH", "amd", 3, "hard"),
    ],
)
def test_amd_probability_mapping(
    prob: float, risk: str, label: str, grade: int, drusen: str
) -> None:
    pred = amd_prediction_from_probability(prob)
    assert pred.risk_level == risk
    assert pred.label == label
    assert pred.amd_grade == grade
    assert pred.drusen_type == drusen
    assert risk_level_from_probability(prob) == risk


def test_prediction_to_result_fields() -> None:
    pred = amd_prediction_from_probability(0.82)
    result = prediction_to_result(pred, ontology_passed=True, decision_mode="legacy")
    assert result.label == "amd"
    assert result.probability == pytest.approx(0.82)
    assert result.risk_level == "HIGH"
    assert result.drusen_type == "hard"
    assert result.model_used == "cnn(efficientnet_b4_amd)"


def test_referral_from_risk() -> None:
    assert referral_from_risk("LOW", 0.1) == "none"
    assert referral_from_risk("MODERATE", 0.5) == "routine"
    assert referral_from_risk("HIGH", 0.75) == "urgent"
    assert referral_from_risk("HIGH", 0.9) == "immediate"


def test_amd_ontology_sem_rules() -> None:
    import asyncio

    from services.amd_cnn import amd_prediction_from_probability
    from services.amd_ontology import build_amd_ontology_payload, validate_amd_ontology

    pred = amd_prediction_from_probability(0.82)
    draft = prediction_to_result(pred)
    payload = build_amd_ontology_payload(
        pred,
        model_used="cnn(efficientnet_b4_amd)",
        icd10_code=draft.icd10_code,
        referral_urgency=draft.referral_urgency,
    )
    result = asyncio.run(validate_amd_ontology(payload))
    assert result.passed is True


def test_amd_ontology_rejects_bad_referral() -> None:
    import asyncio

    from services.amd_ontology import validate_amd_ontology

    payload = {
        "task": "amd",
        "amd_grade": 2,
        "grade_label": "intermediate",
        "label": "amd",
        "probability": 0.82,
        "confidence": 0.82,
        "risk_level": "HIGH",
        "drusen_type": "hard",
        "vision_impact": "moderate",
        "icd10_code": "H35.31",
        "referral_urgency": "none",
        "model_used": "cnn(efficientnet_b4_amd)",
    }
    result = asyncio.run(validate_amd_ontology(payload))
    assert result.passed is False
    codes = [e.code for e in result.errors]
    assert "AMD-SEM-004" in codes
