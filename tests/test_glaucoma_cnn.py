"""
파일명: test_glaucoma_cnn.py
목적: Glaucoma CNN (glaucoma_v2 ONNX) 추론 검증
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가


Glaucoma CNN 매핑·API smoke.
"""
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


def test_decision_gate_hard_reject() -> None:
    import asyncio

    from services.diagnosis_pipeline import apply_four_agent_glaucoma_decision
    from services.glaucoma_ontology import build_glaucoma_ontology_payload

    pred = glaucoma_prediction_from_probability(0.48)
    draft = prediction_to_result(pred)
    payload = build_glaucoma_ontology_payload(
        pred,
        model_used="cnn(efficientnet_b4_glaucoma)",
        icd10_code=draft.icd10_code,
        referral_urgency=draft.referral_urgency,
    )
    onto, audit, mode = asyncio.run(
        apply_four_agent_glaucoma_decision(
            probability=pred.probability,
            confidence=pred.confidence,
            label=pred.label,
            glaucoma_grade=pred.glaucoma_grade,
            patient_id="test-patient",
            ontology_payload=payload,
        )
    )
    assert onto is False
    assert audit["decision"] == "REJECT"
    assert mode == "gate"
    assert audit["threshold"] == 0.65


def test_decision_gate_revise_band() -> None:
    import asyncio

    from services.diagnosis_pipeline import apply_four_agent_glaucoma_decision
    from services.glaucoma_ontology import build_glaucoma_ontology_payload

    pred = glaucoma_prediction_from_probability(0.60)
    draft = prediction_to_result(pred)
    payload = build_glaucoma_ontology_payload(
        pred,
        model_used="cnn(efficientnet_b4_glaucoma)",
        icd10_code=draft.icd10_code,
        referral_urgency=draft.referral_urgency,
    )
    onto, audit, mode = asyncio.run(
        apply_four_agent_glaucoma_decision(
            probability=pred.probability,
            confidence=pred.confidence,
            label=pred.label,
            glaucoma_grade=pred.glaucoma_grade,
            patient_id="test-patient",
            ontology_payload=payload,
        )
    )
    assert onto is True
    assert audit["decision"] == "REVISE"
    assert mode == "gate"


def test_decision_gate_high_confidence_passes_gate() -> None:
    import asyncio

    from services.diagnosis_pipeline import apply_four_agent_glaucoma_decision
    from services.glaucoma_ontology import build_glaucoma_ontology_payload

    pred = glaucoma_prediction_from_probability(0.85)
    draft = prediction_to_result(pred)
    payload = build_glaucoma_ontology_payload(
        pred,
        model_used="cnn(efficientnet_b4_glaucoma)",
        icd10_code=draft.icd10_code,
        referral_urgency=draft.referral_urgency,
    )
    _, audit, mode = asyncio.run(
        apply_four_agent_glaucoma_decision(
            probability=pred.probability,
            confidence=pred.confidence,
            label=pred.label,
            glaucoma_grade=pred.glaucoma_grade,
            patient_id="test-patient",
            ontology_payload=payload,
        )
    )
    assert audit.get("threshold") == 0.65
    if mode == "gate":
        assert audit["decision"] != "REJECT"
