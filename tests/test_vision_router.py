"""
파일명: test_vision_router.py
목적: vision router.py 단위·통합 테스트
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가


VISION multi-modal 라우팅 + CONSENSUS 병합 테스트 (D R3 D3).

Mock 0 — LLM/네트워크 호출 없음. ``merge_consensus`` 및 env 로더만 검증.
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit

from services.vision_router import (
    VisionRoutingConfig,
    load_vision_config,
    merge_consensus,
)


def test_load_vision_config_single_default() -> None:
    env = {"MEDI_VISION_MODE": "single", "MEDI_VISION_MODELS": ""}
    with patch.dict(os.environ, env, clear=True):
        cfg = load_vision_config()
    assert cfg.mode == "single"
    assert len(cfg.model_ids) == 1


def test_load_vision_config_auto_consensus_when_two_models() -> None:
    env = {
        "MEDI_VISION_MODE": "single",
        "MEDI_VISION_MODELS": "model-a,model-b",
        "MEDI_VISION_CONSENSUS_MIN_AGREE": "2",
    }
    with patch.dict(os.environ, env, clear=True):
        cfg = load_vision_config()
    assert cfg.mode == "consensus"
    assert cfg.model_ids == ("model-a", "model-b")
    assert cfg.consensus_min_agree == 2


def test_merge_consensus_majority_icd_and_max_severity() -> None:
    parsed = [
        {
            "icd10_code": "H36.0",
            "severity": "mild",
            "confidence": 0.8,
            "condition": "diabetic_retinopathy",
            "condition_kr": "당뇨망막병증",
        },
        {
            "icd10_code": "H36.0",
            "severity": "moderate",
            "confidence": 0.75,
            "condition": "diabetic_retinopathy",
            "condition_kr": "당뇨망막병증",
        },
        {
            "icd10_code": "H35.3",
            "severity": "severe",
            "confidence": 0.9,
            "condition": "amd",
            "condition_kr": "황반변성",
        },
    ]
    merged = merge_consensus(
        parsed,
        model_ids=("gemma-vision", "mistral-7b", "gemma-fast"),
        min_agree=2,
    )
    assert merged["icd10_code"] == "H36.0"
    assert merged["severity"] == "moderate"
    assert merged["confidence"] == pytest.approx(0.775, abs=0.01)
    assert merged["model_used"].startswith("consensus(")
    assert "consensus" in merged["model_used"]


def test_merge_consensus_single_passthrough() -> None:
    one = [
        {
            "icd10_code": "H40.1",
            "severity": "moderate",
            "confidence": 0.82,
            "condition": "glaucoma",
            "condition_kr": "녹내장",
        }
    ]
    merged = merge_consensus(one, model_ids=("solo-model",), min_agree=1)
    assert merged["icd10_code"] == "H40.1"
    assert merged["model_used"] == "solo-model"


def test_routing_config_is_consensus_flag() -> None:
    cfg = VisionRoutingConfig(
        mode="consensus",
        model_ids=("a", "b"),
        consensus_min_agree=2,
    )
    assert cfg.is_consensus is True
    cfg_single = VisionRoutingConfig(
        mode="single",
        model_ids=("a",),
        consensus_min_agree=1,
    )
    assert cfg_single.is_consensus is False
