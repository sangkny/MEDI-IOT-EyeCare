"""Glaucoma CNN 매핑·API smoke."""
from __future__ import annotations

import pytest

from services.glaucoma_cnn import (
    glaucoma_prediction_from_probability,
    prediction_to_result,
    risk_level_from_probability,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "prob, risk, label, grade",
    [
        (0.1, "LOW", "normal", 0),
        (0.5, "MODERATE", "glaucoma", 1),
        (0.8, "HIGH", "glaucoma", 2),
    ],
)
def test_glaucoma_probability_mapping(
    prob: float, risk: str, label: str, grade: int
) -> None:
    pred = glaucoma_prediction_from_probability(prob)
    assert pred.risk_level == risk
    assert pred.label == label
    assert pred.glaucoma_grade == grade
    assert risk_level_from_probability(prob) == risk


def test_prediction_to_result_fields() -> None:
    pred = glaucoma_prediction_from_probability(0.82)
    result = prediction_to_result(pred, ontology_passed=True, decision_mode="legacy")
    assert result.label == "glaucoma"
    assert result.probability == pytest.approx(0.82)
    assert result.risk_level == "HIGH"
    assert result.confidence >= 0.8


def test_decision_gate_reject() -> None:
    import asyncio

    from services.diagnosis_pipeline import apply_four_agent_glaucoma_decision

    onto, audit, mode = asyncio.run(
        apply_four_agent_glaucoma_decision(
            probability=0.55,
            confidence=0.55,
            label="glaucoma",
            glaucoma_grade=1,
            patient_id="test-patient",
        )
    )
    assert onto is False
    assert audit["decision"] == "REJECT"
    assert mode == "gate"
    assert audit["threshold"] == 0.80


def test_decision_gate_high_confidence_passes_gate() -> None:
    import asyncio

    from services.diagnosis_pipeline import apply_four_agent_glaucoma_decision

    _, audit, mode = asyncio.run(
        apply_four_agent_glaucoma_decision(
            probability=0.85,
            confidence=0.85,
            label="glaucoma",
            glaucoma_grade=2,
            patient_id="test-patient",
        )
    )
    assert audit.get("threshold") == 0.80
    if mode == "gate":
        assert audit["decision"] != "REJECT"
