"""
파일명: test_comprehensive_modes.py
목적: fast/precise 모드 분기 — inference_mode, inference_time_ms
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가


comprehensive fast/precise 모드 라우팅 · inference 메타 단위 테스트.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def test_attach_inference_meta_sets_mode_and_time() -> None:
    from schemas.integrated_diagnosis import (
        ComprehensiveFundusResponse,
        DRComprehensiveSummary,
        OverallAssessment,
    )
    from services.comprehensive_fundus import _attach_inference_meta

    dr = DRComprehensiveSummary(dr_grade=0, confidence=0.9, icd10_code="H35.0", severity="normal")
    resp = ComprehensiveFundusResponse(
        dr=dr,
        overall_assessment=OverallAssessment(recommendation="ok"),
    )
    out = _attach_inference_meta(resp, mode_label="fast(v10)", t0=0.0)
    assert out.overall_assessment.inference_mode == "fast(v10)"
    assert out.overall_assessment.inference_time_ms is not None
    assert out.overall_assessment.inference_time_ms >= 0


@pytest.mark.asyncio
async def test_fast_mode_default_uses_v10() -> None:
    from schemas.integrated_diagnosis import DRComprehensiveSummary
    from services.comprehensive_fundus import run_comprehensive_fundus
    from services.retinal_cnn import DrPrediction
    from services.v10_cnn import V10Prediction

    dr = DrPrediction(
        dr_grade=1,
        confidence=0.8,
        icd10_code="H35.0",
        severity="mild",
        probabilities=(0.2, 0.8, 0.0, 0.0, 0.0),
    )
    mock_v10 = V10Prediction(
        dr=dr,
        glaucoma=MagicMock(probability=0.2, confidence=0.8, label="normal", glaucoma_grade=0),
        amd=MagicMock(probability=0.1, confidence=0.9, label="normal", amd_grade=0),
        myopia=MagicMock(probability=0.1, confidence=0.9, label="normal", myopia_grade=0),
        multidisease=MagicMock(probabilities={}, class_names=tuple()),
    )

    with (
        patch("services.comprehensive_fundus.is_v10_available", return_value=True),
        patch(
            "services.comprehensive_fundus.predict_v10_from_image_bytes",
            new=AsyncMock(return_value=mock_v10),
        ),
        patch(
            "services.comprehensive_fundus._run_glaucoma_pipeline",
            new=AsyncMock(return_value=(None, None)),
        ),
        patch(
            "services.comprehensive_fundus._run_amd_pipeline",
            new=AsyncMock(return_value=(None, None)),
        ),
        patch(
            "services.comprehensive_fundus._run_myopia_pipeline",
            new=AsyncMock(return_value=(None, None)),
        ),
        patch(
            "services.comprehensive_fundus.prediction_to_screening_result",
            return_value=None,
        ),
        patch(
            "services.comprehensive_fundus.get_v10_backend",
            return_value=MagicMock(model_label=lambda: "efficientnet_b4_v10"),
        ),
    ):
        resp = await run_comprehensive_fundus(b"fake-image", include_heatmap=False)
    assert resp.input_format == "v10_onnx"
    assert resp.overall_assessment.inference_mode == "fast(v10)"
    assert resp.overall_assessment.inference_time_ms is not None


@pytest.mark.asyncio
async def test_precise_mode_skips_v10_pipeline() -> None:
    from schemas.integrated_diagnosis import GlaucomaResult
    from services.comprehensive_fundus import run_comprehensive_fundus

    glaucoma_result = GlaucomaResult(
        glaucoma_grade=0,
        grade_label="normal",
        label="normal",
        probability=0.2,
        risk_level="LOW",
        confidence=0.9,
        decision="APPROVE",
    )

    with (
        patch("services.comprehensive_fundus.is_v10_available", return_value=True),
        patch(
            "services.comprehensive_fundus._run_comprehensive_v10",
            new=AsyncMock(side_effect=AssertionError("v10 must not run in precise mode")),
        ),
        patch(
            "services.comprehensive_fundus._run_glaucoma_pipeline",
            new=AsyncMock(return_value=(glaucoma_result, None)),
        ),
    ):
        resp = await run_comprehensive_fundus(
            b"fake-image",
            mode="precise",
            tasks=["glaucoma"],
            include_heatmap=False,
        )

    assert resp.overall_assessment.inference_mode == "precise(5-model)"
    assert resp.glaucoma is glaucoma_result


@pytest.mark.asyncio
async def test_invalid_mode_falls_back_to_fast_label_on_legacy() -> None:
    from schemas.integrated_diagnosis import GlaucomaResult
    from services.comprehensive_fundus import run_comprehensive_fundus

    glaucoma_result = GlaucomaResult(
        glaucoma_grade=0,
        grade_label="normal",
        label="normal",
        probability=0.2,
        risk_level="LOW",
        confidence=0.9,
        decision="APPROVE",
    )

    with (
        patch("services.comprehensive_fundus.is_v10_available", return_value=False),
        patch(
            "services.comprehensive_fundus._run_glaucoma_pipeline",
            new=AsyncMock(return_value=(glaucoma_result, None)),
        ),
    ):
        resp = await run_comprehensive_fundus(
            b"fake-image",
            mode="turbo",
            tasks=["glaucoma"],
            include_heatmap=False,
        )

    assert resp.overall_assessment.inference_mode == "fast(fallback-5-model)"
