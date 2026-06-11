"""
파일명: test_multidisease_cnn.py
목적: multidisease cnn.py 단위·통합 테스트
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가


다질환 CNN + MULTI-SEM 온톨로지 단위 테스트.
"""
from __future__ import annotations

import asyncio

import pytest

from services.multidisease_cnn import (
    DISEASE_MAP,
    MultidiseasePrediction,
    get_multidisease_threshold,
    is_normal_screening,
    prediction_to_screening_result,
    referral_urgency_from_findings,
    risk_level_from_probability,
)
from services.multidisease_ontology import (
    apply_multidisease_ontology,
    build_multidisease_ontology_payload,
    validate_multidisease_ontology,
)
from training.make_manifest import MULTIDISEASE_TRAIN_CLASSES

pytestmark = pytest.mark.unit


def _sample_probs(**overrides: float) -> dict[str, float]:
    base = {name: 0.05 for name in MULTIDISEASE_TRAIN_CLASSES}
    base.update(overrides)
    return base


def test_disease_map_covers_28_classes() -> None:
    assert len(DISEASE_MAP) == 28
    for name in MULTIDISEASE_TRAIN_CLASSES:
        assert name in DISEASE_MAP
        korean, icd = DISEASE_MAP[name]
        assert korean
        assert icd


def test_prediction_to_screening_result_structure() -> None:
    pred = MultidiseasePrediction(
        probabilities=_sample_probs(crvo=0.82, dr=0.35, armd=0.12),
        class_names=MULTIDISEASE_TRAIN_CLASSES,
    )
    result = prediction_to_screening_result(pred, threshold=0.3)
    assert result.total_diseases_detected == 2
    assert "crvo" in result.urgent_diseases
    assert result.normal is False
    assert len(result.top_findings) <= 3
    assert result.top_findings[0].disease == "crvo"
    assert result.top_findings[0].korean_name == "중심망막정맥폐쇄"
    assert result.model_used == "cnn(efficientnet_b4_multidisease)"


def test_normal_when_all_below_threshold() -> None:
    probs = _sample_probs()
    assert is_normal_screening(probs, threshold=0.3) is True
    result = prediction_to_screening_result(
        MultidiseasePrediction(probabilities=probs, class_names=MULTIDISEASE_TRAIN_CLASSES),
        threshold=0.3,
    )
    assert result.normal is True
    assert result.findings == []
    assert result.referral_urgency == "none"


def test_risk_level_and_referral_mapping() -> None:
    assert risk_level_from_probability(0.2) == "low"
    assert risk_level_from_probability(0.4) == "moderate"
    assert risk_level_from_probability(0.6) == "high"
    assert risk_level_from_probability(0.8) == "urgent"
    probs = _sample_probs(aion=0.55)
    assert referral_urgency_from_findings(probs, urgent_diseases=[]) == "immediate"


def test_multi_sem_001_emergency_referral() -> None:
    pred = MultidiseasePrediction(
        probabilities=_sample_probs(crvo=0.62),
        class_names=MULTIDISEASE_TRAIN_CLASSES,
    )
    draft = prediction_to_screening_result(pred, threshold=0.3, referral_urgency="routine")
    payload = build_multidisease_ontology_payload(
        pred,
        screening=draft,
        model_used="cnn(efficientnet_b4_multidisease)",
        threshold=0.3,
    )
    result = asyncio.run(validate_multidisease_ontology(payload))
    codes = {e.code for e in result.errors}
    assert "MULTI-SEM-001" in codes


def test_multi_sem_002_dr_armd_compound() -> None:
    pred = MultidiseasePrediction(
        probabilities=_sample_probs(dr=0.45, armd=0.52),
        class_names=MULTIDISEASE_TRAIN_CLASSES,
    )
    draft = prediction_to_screening_result(pred, threshold=0.3)
    payload = build_multidisease_ontology_payload(
        pred,
        screening=draft,
        model_used="cnn(efficientnet_b4_multidisease)",
        threshold=0.3,
    )
    result = asyncio.run(validate_multidisease_ontology(payload))
    assert any(w.code == "MULTI-SEM-002" for w in result.warnings)


def test_multi_sem_003_normal_consistency() -> None:
    probs = _sample_probs()
    pred = MultidiseasePrediction(probabilities=probs, class_names=MULTIDISEASE_TRAIN_CLASSES)
    draft = prediction_to_screening_result(pred, threshold=0.3)
    bad = draft.model_copy(update={"normal": False})
    payload = build_multidisease_ontology_payload(
        pred,
        screening=bad,
        threshold=get_multidisease_threshold(),
    )
    result = asyncio.run(validate_multidisease_ontology(payload))
    assert any(e.code == "MULTI-SEM-003" for e in result.errors)


def test_apply_multidisease_ontology_sets_immediate() -> None:
    pred = MultidiseasePrediction(
        probabilities=_sample_probs(aion=0.61),
        class_names=MULTIDISEASE_TRAIN_CLASSES,
    )
    draft = prediction_to_screening_result(pred, threshold=0.3, referral_urgency="routine")
    payload = build_multidisease_ontology_payload(
        pred,
        screening=draft,
        threshold=0.3,
    )
    final = asyncio.run(apply_multidisease_ontology(payload, draft))
    assert final.referral_urgency == "immediate"
