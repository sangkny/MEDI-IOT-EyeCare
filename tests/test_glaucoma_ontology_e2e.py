"""
파일명: test_glaucoma_ontology_e2e.py
목적: 녹내장 ontology 전체 흐름 E2E 회귀
      CNN(mock probability) → CDR 근사 → ontology payload
      → validate / four_agent decision → ontology_passed
히스토리:
  2026-06-22 - 최초 작성 (온톨로지 진단 — E2E 회귀 보강)
"""
from __future__ import annotations

import pytest

from services.cdr_estimator import ProbabilityBasedCDR
from services.diagnosis_pipeline import apply_four_agent_glaucoma_decision
from services.glaucoma_cnn import glaucoma_prediction_from_probability, prediction_to_result
from services.glaucoma_ontology import (
    build_glaucoma_ontology_payload,
    validate_glaucoma_ontology,
)

pytestmark = pytest.mark.unit


async def _run_glaucoma_ontology_e2e(
    probability: float,
    *,
    patient_id: str = "e2e-patient",
) -> tuple[bool, dict, dict]:
    """운영 경로와 동일: probability → CDR → payload → validate → decision."""
    import numpy as np

    pred = glaucoma_prediction_from_probability(probability)
    draft = prediction_to_result(pred, ontology_passed=True, decision_mode="pending")

    cdr = await ProbabilityBasedCDR().estimate(
        np.zeros((1, 1, 3), dtype=np.uint8), pred.probability
    )
    cdr_dict = cdr.to_dict()

    payload = build_glaucoma_ontology_payload(
        pred,
        model_used="cnn(mock-e2e)",
        icd10_code=draft.icd10_code,
        referral_urgency=draft.referral_urgency,
        cup_disc_ratio=cdr_dict,
    )
    validation = await validate_glaucoma_ontology(payload)
    onto, audit, mode = await apply_four_agent_glaucoma_decision(
        probability=pred.probability,
        confidence=pred.confidence,
        label=pred.label,
        glaucoma_grade=pred.glaucoma_grade,
        patient_id=patient_id,
        ontology_payload=payload,
    )
    return onto, audit, {
        "validation_passed": validation.passed,
        "cdr": cdr_dict,
        "risk_level": pred.risk_level,
    }


@pytest.mark.asyncio
async def test_e2e_clear_normal_low_prob(monkeypatch: pytest.MonkeyPatch) -> None:
    """명확한 정상(낮은 prob, 낮은 CDR) → ontology_passed=true."""
    import services.diagnosis_pipeline as dp

    monkeypatch.setattr(
        dp,
        "_pipeline",
        (type("F", (), {"is_four_agent_enabled": staticmethod(lambda _r: False)})(), object),
    )
    onto, audit, meta = await _run_glaucoma_ontology_e2e(0.12)
    assert meta["validation_passed"] is True
    assert audit["ontology_passed"] is True
    assert meta["risk_level"] == "LOW"
    assert meta["cdr"]["category"] == "normal"
    assert onto is True
    assert audit["decision"] == "APPROVE"


@pytest.mark.asyncio
async def test_e2e_clear_abnormal_high_prob(monkeypatch: pytest.MonkeyPatch) -> None:
    """명확한 이상(높은 prob, 높은 CDR) → HIGH risk · ontology 통과."""
    monkeypatch.setenv("AGENT_FOUR_AGENT_MOCK", "1")
    onto, audit, meta = await _run_glaucoma_ontology_e2e(0.88)
    assert meta["validation_passed"] is True
    assert audit["ontology_passed"] is True
    assert meta["risk_level"] == "HIGH"
    assert meta["cdr"]["category"] == "glaucoma"
    assert onto is True
    assert audit["decision"] in ("APPROVE", "REVISE")


@pytest.mark.asyncio
async def test_e2e_borderline_glau_sem_005_consistency(monkeypatch: pytest.MonkeyPatch) -> None:
    """경계: ontology payload에 CDR·risk 불일치 주입 시 GLAU-SEM-005."""
    monkeypatch.setenv("AGENT_FOUR_AGENT_MOCK", "1")
    pred = glaucoma_prediction_from_probability(0.85)
    draft = prediction_to_result(pred)
    bad_cdr = {"value": 0.82, "category": "glaucoma", "method": "probability_based"}
    payload = build_glaucoma_ontology_payload(
        pred,
        model_used="cnn(mock-e2e)",
        icd10_code=draft.icd10_code,
        referral_urgency="routine",
        cup_disc_ratio=bad_cdr,
    )
    payload["risk_level"] = "MODERATE"

    validation = await validate_glaucoma_ontology(payload)
    assert not validation.passed
    assert any(e.code == "GLAU-SEM-005" for e in validation.errors)

    onto, audit, _ = await apply_four_agent_glaucoma_decision(
        probability=pred.probability,
        confidence=pred.confidence,
        label=pred.label,
        glaucoma_grade=pred.glaucoma_grade,
        patient_id="e2e-border",
        ontology_payload=payload,
    )
    assert audit["ontology_passed"] is False
    assert onto is False
    assert audit["decision"] == "REJECT"
    assert audit["mode"] == "ontology"
