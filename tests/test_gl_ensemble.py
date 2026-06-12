"""
목적: GlaucomaEnsemble 단위 테스트
히스토리:
  2026-06-12 - 최초 작성 (D+B GL 개선 계획)
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from services.gl_ensemble import GlaucomaEnsemble
from services.glaucoma_cnn import glaucoma_prediction_from_probability, prediction_to_result

pytestmark = pytest.mark.unit


@dataclass
class _MockV2:
    v2_prob: float = 0.60
    called: bool = False

    def predict_sync(self, image_bytes: bytes):
        self.called = True
        return glaucoma_prediction_from_probability(self.v2_prob)


@pytest.mark.asyncio
async def test_certain_normal_skips_v2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDI_GL_ENSEMBLE_ENABLED", "1")
    mock = _MockV2()
    out = await GlaucomaEnsemble().predict(
        image_bytes=b"img",
        v10c_prob=0.15,
        glaucoma_v2_model=mock,
    )
    assert out["method"] == "v10c_certain_normal"
    assert out["probability"] == pytest.approx(0.15)
    assert out["v2_prob"] is None
    assert not mock.called


@pytest.mark.asyncio
async def test_certain_abnormal_skips_v2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDI_GL_ENSEMBLE_ENABLED", "1")
    mock = _MockV2()
    out = await GlaucomaEnsemble().predict(
        image_bytes=b"img",
        v10c_prob=0.80,
        glaucoma_v2_model=mock,
    )
    assert out["method"] == "v10c_certain_abnormal"
    assert out["probability"] == pytest.approx(0.80)
    assert out["v2_prob"] is None
    assert not mock.called


@pytest.mark.asyncio
async def test_uncertain_runs_ensemble(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDI_GL_ENSEMBLE_ENABLED", "1")
    mock = _MockV2(v2_prob=0.60)
    out = await GlaucomaEnsemble().predict(
        image_bytes=b"img",
        v10c_prob=0.50,
        glaucoma_v2_model=mock,
    )
    assert out["method"] == "ensemble_v10c_v2"
    assert mock.called
    assert out["v2_prob"] == pytest.approx(0.60)
    assert out["ensemble_weight"] == {"v10c": 0.35, "v2": 0.65}


@pytest.mark.asyncio
async def test_ensemble_weighted_average(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDI_GL_ENSEMBLE_ENABLED", "1")
    mock = _MockV2(v2_prob=0.60)
    out = await GlaucomaEnsemble().predict(
        image_bytes=b"img",
        v10c_prob=0.50,
        glaucoma_v2_model=mock,
    )
    expected = 0.50 * 0.35 + 0.60 * 0.65
    assert out["probability"] == pytest.approx(round(expected, 6))


def test_inference_detail_structure() -> None:
    detail = {
        "v10c_prob": 0.605,
        "v2_prob": 0.623,
        "method": "ensemble_v10c_v2",
        "ensemble_weight": {"v10c": 0.35, "v2": 0.65},
    }
    pred = glaucoma_prediction_from_probability(0.612)
    result = prediction_to_result(pred, inference_detail=detail)
    assert result.inference_detail == detail
    assert result.inference_detail["method"] == "ensemble_v10c_v2"


def test_certain_interval_v2_prob_none() -> None:
    detail = {
        "v10c_prob": 0.15,
        "v2_prob": None,
        "method": "v10c_certain_normal",
        "ensemble_weight": None,
    }
    pred = glaucoma_prediction_from_probability(0.15)
    result = prediction_to_result(pred, inference_detail=detail)
    assert result.inference_detail["v2_prob"] is None
    assert result.inference_detail["ensemble_weight"] is None
