"""Retinal CNN 단위 테스트 (D R4-ML D2, Mock 0)."""
from __future__ import annotations

import json

import pytest

pytestmark = [pytest.mark.requires_onnx, pytest.mark.integration]

from services.retinal_cnn import (
    DR_NUM_CLASSES,
    dr_prediction_from_logits,
)


def test_dr_prediction_from_list_logits() -> None:
    """torch 없이 list logits → softmax·argmax."""
    logits = [0.1, 0.2, 3.0, 0.5, 0.1]
    pred = dr_prediction_from_logits(logits)
    assert pred.dr_grade == 2
    assert pred.icd10_code == "H36.0"
    assert pred.severity == "moderate"
    assert len(pred.probabilities) == DR_NUM_CLASSES
    assert abs(sum(pred.probabilities) - 1.0) < 1e-5


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("torch"),
    reason="torch not installed",
)
def test_efficientnet_forward_shape() -> None:
    import torch

    from services.retinal_cnn import build_dr_classifier, resolve_cnn_arch

    model, arch = build_dr_classifier(arch="efficientnet_b0", pretrained=False)
    assert arch == resolve_cnn_arch("efficientnet_b0")
    model.eval()
    x = torch.randn(2, 3, 224, 224)
    out = model(x)
    assert out.shape == (2, DR_NUM_CLASSES)
    pred = dr_prediction_from_logits(out[0])
    assert 0 <= pred.dr_grade < DR_NUM_CLASSES


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("torch"),
    reason="torch not installed",
)
def test_train_smoke_writes_artifacts(tmp_path) -> None:
    import sys
    import types
    from pathlib import Path

    scripts = Path(__file__).resolve().parent.parent / "scripts"
    sys.path.insert(0, str(scripts))
    import train_retinal as tr

    out = tmp_path / "models"
    args = types.SimpleNamespace(
        smoke=True,
        manifest="",
        split="train",
        output_dir=str(out),
        epochs=1,
        batch_size=4,
        lr=1e-3,
        image_size=64,
        arch="efficientnet_b4",
        synthetic_samples=8,
    )
    assert tr.train_and_export(args) == 0
    assert (out / "retinal_v1.pt").is_file()
    assert (out / "retinal_v1.onnx").is_file()
    meta = json.loads((out / "retinal_v1.meta.json").read_text(encoding="utf-8"))
    assert meta.get("arch") == "efficientnet_b4"


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("torch"),
    reason="torch not installed",
)
def test_efficientnet_b4_forward_shape() -> None:
    import torch

    from services.retinal_cnn import build_dr_classifier

    model, arch = build_dr_classifier(arch="efficientnet_b4", pretrained=False)
    assert arch == "efficientnet_b4"
    model.eval()
    x = torch.randn(1, 3, 224, 224)
    out = model(x)
    assert out.shape == (1, DR_NUM_CLASSES)
