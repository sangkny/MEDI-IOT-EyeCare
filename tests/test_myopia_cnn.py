"""근시 CNN 매핑·온톨로지·API smoke."""
from __future__ import annotations

import pytest

from services.myopia_cnn import (
    AXIAL_LENGTH_BY_GRADE,
    myopia_prediction_from_probability,
    prediction_to_result,
    referral_from_risk,
    risk_level_from_probability,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "prob, risk, label, grade, pathological",
    [
        (0.1, "LOW", "normal", 0, False),
        (0.4, "MODERATE", "normal", 1, False),
        (0.55, "MODERATE", "myopia", 2, False),
        (0.8, "HIGH", "myopia", 3, True),
    ],
)
def test_myopia_probability_mapping(
    prob: float, risk: str, label: str, grade: int, pathological: bool
) -> None:
    pred = myopia_prediction_from_probability(prob)
    assert pred.risk_level == risk
    assert pred.label == label
    assert pred.myopia_grade == grade
    assert pred.pathological is pathological
    assert pred.axial_length_estimate == AXIAL_LENGTH_BY_GRADE[grade]
    assert risk_level_from_probability(prob) == risk


def test_prediction_to_result_fields() -> None:
    pred = myopia_prediction_from_probability(0.72)
    result = prediction_to_result(pred, ontology_passed=True, decision_mode="legacy")
    assert result.label == "myopia"
    assert result.probability == pytest.approx(0.72)
    assert result.risk_level == "HIGH"
    assert result.myopia_grade == 3
    assert result.icd10_code == "H44.2"
    assert result.model_used == "cnn(efficientnet_b4_myopia)"


def test_referral_from_risk() -> None:
    assert referral_from_risk("LOW", 0.1) == "none"
    assert referral_from_risk("MODERATE", 0.5) == "routine"
    assert referral_from_risk("HIGH", 0.75) == "urgent"
    assert referral_from_risk("HIGH", 0.9) == "immediate"


def test_myopia_ontology_sem_rules() -> None:
    import asyncio

    from services.myopia_ontology import build_myopia_ontology_payload, validate_myopia_ontology

    pred = myopia_prediction_from_probability(0.72)
    draft = prediction_to_result(pred)
    payload = build_myopia_ontology_payload(
        pred,
        model_used="cnn(efficientnet_b4_myopia)",
        icd10_code=draft.icd10_code,
        referral_urgency=draft.referral_urgency,
    )
    result = asyncio.run(validate_myopia_ontology(payload))
    assert result.passed is True


def test_myopia_ontology_rejects_bad_referral() -> None:
    import asyncio

    from services.myopia_ontology import validate_myopia_ontology

    payload = {
        "task": "myopia",
        "myopia_grade": 2,
        "grade_label": "moderate",
        "label": "myopia",
        "probability": 0.62,
        "confidence": 0.62,
        "risk_level": "MODERATE",
        "axial_length_estimate": 26.5,
        "vision_impact": "moderate",
        "icd10_code": "H52.1",
        "referral_urgency": "none",
        "model_used": "cnn(efficientnet_b4_myopia)",
    }
    result = asyncio.run(validate_myopia_ontology(payload))
    assert result.passed is False
    codes = [e.code for e in result.errors]
    assert "MYO-SEM-004" in codes
