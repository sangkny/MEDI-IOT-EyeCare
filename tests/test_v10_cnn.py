"""v10_cnn · comprehensive v10 경로 단위 테스트."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def test_is_v10_available_false_when_missing(monkeypatch) -> None:
    from services import v10_cnn

    monkeypatch.setenv("MEDI_V10_ENABLED", "auto")
    monkeypatch.setattr(v10_cnn, "get_v10_model_path", lambda: __import__("pathlib").Path("/nonexistent/v10.onnx"))
    assert v10_cnn.is_v10_available() is False


@pytest.mark.asyncio
async def test_run_comprehensive_uses_v10_when_available() -> None:
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
    assert isinstance(resp.dr, DRComprehensiveSummary)
    assert resp.dr.grade == 1
    assert resp.overall_assessment.inference_mode == "fast(v10)"
