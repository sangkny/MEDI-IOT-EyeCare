"""
파일명: test_retinal_preprocess.py
목적: retinal preprocess.py 단위·통합 테스트
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가


Retinal 전처리·MSEF-Net 단위 테스트 (D R4-ML D4, Mock 0).
"""
from __future__ import annotations

import numpy as np
import pytest

pytestmark = pytest.mark.unit

from services.retinal_cnn import (
    apply_clahe,
    ben_graham_preprocess,
    preprocess_fundus_array,
    resolve_preprocess_mode,
)


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("cv2"),
    reason="opencv not installed",
)
def test_clahe_preserves_shape() -> None:
    img = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
    out = apply_clahe(img)
    assert out.shape == img.shape


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("cv2"),
    reason="opencv not installed",
)
def test_ben_graham_preserves_shape() -> None:
    img = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
    out = ben_graham_preprocess(img)
    assert out.shape == img.shape


def test_preprocess_mode_both() -> None:
    pytest.importorskip("cv2")
    img = np.random.randint(0, 255, (32, 32, 3), dtype=np.uint8)
    out = preprocess_fundus_array(img, mode="both")
    assert out.shape == (32, 32, 3)


def test_resolve_preprocess_default() -> None:
    assert resolve_preprocess_mode("clahe") == "clahe"
    assert resolve_preprocess_mode("none") == "none"
    assert resolve_preprocess_mode("enhanced") == "enhanced"
    assert resolve_preprocess_mode("v2") == "v2"


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("cv2"),
    reason="opencv not installed",
)
def test_preprocess_v2_mode() -> None:
    img = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
    out = preprocess_fundus_array(img, mode="v2")
    assert out.shape == (224, 224, 3)
    assert out.dtype == np.uint8


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("torch"),
    reason="torch not installed",
)
def test_msef_net_forward() -> None:
    import torch

    from services.retinal_cnn import build_dr_classifier

    model, arch = build_dr_classifier(arch="msef_net", pretrained=False)
    assert arch == "msef_net"
    model.eval()
    x = torch.randn(2, 3, 224, 224)
    out = model(x)
    assert out.shape == (2, 5)
