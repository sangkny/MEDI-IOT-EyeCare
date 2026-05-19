"""InferenceRouter 단위 테스트 (D R4-ML D3, Mock 0)."""
from __future__ import annotations

import pytest

from services.eye_analyzer import AnalysisResult
from services.inference_router import (
    load_inference_config,
    merge_ensemble_results,
)
from services.retinal_cnn import dr_prediction_from_logits, dr_prediction_to_parsed


def test_dr_prediction_to_parsed_schema() -> None:
    pred = dr_prediction_from_logits([5.0, 0.1, 0.1, 0.1, 0.1])
    parsed = dr_prediction_to_parsed(pred)
    assert parsed["condition"] == "normal_fundus"
    assert parsed["icd10_code"] == "H57.9"
    assert parsed["severity"] == "normal"
    assert 0.0 <= parsed["confidence"] <= 1.0


def test_merge_ensemble_prefers_cnn_icd_when_confident() -> None:
    cnn = AnalysisResult(
        condition="mild_diabetic_retinopathy",
        condition_kr="경증",
        severity="mild",
        icd10_code="H35.0",
        confidence=0.92,
        raw_analysis="{}",
        model_used="cnn(efficientnet_b4)",
        ontology_passed=True,
        ontology_errors=[],
        exam_type="fundus",
    )
    llm = AnalysisResult(
        condition="other",
        condition_kr="기타",
        severity="moderate",
        icd10_code="H36.0",
        confidence=0.55,
        raw_analysis="{}",
        model_used="consensus(gemma)",
        ontology_passed=True,
        ontology_errors=[],
        exam_type="fundus",
    )
    merged = merge_ensemble_results(cnn, llm, cnn_confidence_min=0.70)
    assert merged.icd10_code == "H35.0"
    assert merged.severity == "moderate"
    assert "ensemble(" in merged.model_used


def test_load_inference_config_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MEDI_INFERENCE_BACKEND", raising=False)
    monkeypatch.delenv("MEDI_CNN_ARCH", raising=False)
    cfg = load_inference_config()
    assert cfg.backend == "llm"
    assert cfg.cnn_arch == "efficientnet_b4"


def test_load_inference_config_cnn_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDI_INFERENCE_BACKEND", "ensemble")
    monkeypatch.setenv("MEDI_CNN_CONFIDENCE_MIN", "0.8")
    cfg = load_inference_config()
    assert cfg.backend == "ensemble"
    assert cfg.cnn_confidence_min == pytest.approx(0.8)
