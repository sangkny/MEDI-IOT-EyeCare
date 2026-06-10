"""export_v10.py · v10c ONNX 5-head 검증."""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[1]
ONNX_CANDIDATES = (
    ROOT / "models" / "retinal_v10c.onnx",
    ROOT / "models" / "retinal_v10.onnx",
)


def _resolve_v10_onnx() -> Path | None:
    for path in ONNX_CANDIDATES:
        if path.is_file():
            return path
    return None


def test_v10_onnx_wrapper_emits_five_heads() -> None:
    pytest.importorskip("torch")
    import torch

    from scripts.export_v10 import V10OnnxWrapper
    from training.train_v10 import MultiTaskV10Model

    model = MultiTaskV10Model(pretrained_imagenet=False)
    wrapper = V10OnnxWrapper(model)
    x = torch.randn(1, 3, 224, 224)
    dr, gl, amd, myo, multi = wrapper(x)
    assert dr.shape == (1, 5)
    assert gl.shape == (1, 1)
    assert amd.shape == (1, 1)
    assert myo.shape == (1, 1)
    assert multi.shape[0] == 1 and multi.shape[1] == 28


def test_export_v10_verify_onnx_shapes() -> None:
    ort = pytest.importorskip("onnxruntime")
    import numpy as np

    from scripts.export_v10 import _verify_onnx

    onnx_path = _resolve_v10_onnx()
    if onnx_path is None:
        pytest.skip("v10 ONNX not present locally")

    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    inp = sess.get_inputs()[0].name
    dummy = np.random.randn(1, 3, 224, 224).astype(np.float32)
    outs = sess.run(None, {inp: dummy})
    assert len(outs) == 5
    assert outs[0].shape == (1, 5)
    assert outs[1].shape == (1, 1)
    assert outs[2].shape == (1, 1)
    assert outs[3].shape == (1, 1)
    assert outs[4].shape == (1, 28)

    _verify_onnx(onnx_path, image_size=224)


def test_v10c_meta_documents_gl_weight() -> None:
    meta_path = ROOT / "models" / "retinal_v10c.meta.json"
    if not meta_path.is_file():
        pytest.skip("retinal_v10c.meta.json not present")
    import json

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta.get("best_composite") == pytest.approx(0.8842, rel=1e-4)
    assert meta.get("best_gl_auc") == pytest.approx(0.835, rel=1e-3)
    lw = meta.get("loss_weights") or {}
    assert lw.get("glaucoma") == pytest.approx(0.28, rel=1e-4)
