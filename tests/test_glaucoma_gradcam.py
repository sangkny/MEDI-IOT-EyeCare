"""Glaucoma GradCAM++ / lesion 주석 단위 테스트."""
from __future__ import annotations

import base64
import io

import pytest

from services.gradcam import (
    GradCAMService,
    _normalize_glaucoma_state_dict,
    generate_glaucoma_annotated_heatmap,
    generate_glaucoma_lesion_annotations,
)

pytestmark = pytest.mark.unit


def test_glaucoma_lesion_annotations_structure() -> None:
    hotspots = [{"x": 0.45, "y": 0.42, "intensity": 0.9}]
    anns = generate_glaucoma_lesion_annotations(
        hotspots, 0.79, eye_side="right"
    )
    assert len(anns) >= 1
    for a in anns:
        assert "type" in a
        assert "confidence" in a
        assert "region" in a
        assert 0.0 <= a["confidence"] <= 1.0


def test_normalize_glaucoma_state_dict_head_to_classifier() -> None:
    pytest.importorskip("torch")
    import torch

    sd = {
        "features.0.weight": torch.zeros(1),
        "head.weight": torch.zeros(1, 1),
        "head.bias": torch.zeros(1),
    }
    mapped = _normalize_glaucoma_state_dict(sd)
    assert "classifier.1.weight" in mapped
    assert "classifier.1.bias" in mapped
    assert "head.weight" not in mapped


def test_gradcam_service_detect_model_type() -> None:
    assert GradCAMService.detect_model_type("models/retinal_glaucoma_v2.onnx") == "glaucoma"
    assert GradCAMService.detect_model_type("models/retinal_v4.onnx") == "dr"


def test_generate_glaucoma_heatmap_minimal_image() -> None:
    pytest.importorskip("cv2")
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL not installed")

    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color=(128, 64, 32)).save(buf, format="JPEG")
    image_bytes = buf.getvalue()

    result = generate_glaucoma_annotated_heatmap(
        image_bytes, 0.79, glaucoma_grade=2, eye_side="right"
    )
    assert result.get("heatmap_error") is None or result.get("image_base64")
    if result.get("image_base64"):
        raw = base64.b64decode(result["image_base64"])
        assert len(raw) > 100
    assert len(result.get("lesion_annotations") or []) >= 1
    assert len(result.get("hotspot_regions") or []) >= 1
    assert result.get("gradcam_version") in ("gradcam++", "probability_guided", None)
