"""
목적: fundus_enhancement v2 단위 테스트
히스토리:
  2026-06-12 - v1 EnhanceMode 테스트
  2026-06-13 - v2 함수 테스트로 교체

실행 (Docker 필수, LM Studio 불필요):
  docker exec medi-iot-api-dev python -m pytest tests/test_fundus_enhancement.py -v
"""
from __future__ import annotations

import cv2
import numpy as np
import pytest

from services.fundus_enhancement import (
    center_crop_square,
    enhance_fundus,
    unsharp_masking,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def sample_bgr() -> np.ndarray:
    h, w = 200, 320
    rng = np.random.default_rng(42)
    img = rng.integers(20, 180, (h, w, 3), dtype=np.uint8)
    cv2.circle(img, (w // 2, h // 2), min(h, w) // 3, (40, 120, 180), -1)
    cv2.GaussianBlur(img, (15, 15), 4, dst=img)
    return img


def test_center_crop_square_output_shape(sample_bgr: np.ndarray) -> None:
    out = center_crop_square(sample_bgr)
    assert out.shape[0] == out.shape[1]
    assert out.shape[0] == min(sample_bgr.shape[:2])


def test_enhance_fundus_output_shape(sample_bgr: np.ndarray) -> None:
    out = enhance_fundus(sample_bgr, size=224)
    assert out.shape == (224, 224, 3)
    assert out.dtype == np.uint8


def test_unsharp_rgb_all_channels(sample_bgr: np.ndarray) -> None:
    base = sample_bgr.copy()
    out = unsharp_masking(base, channels="RGB", threshold=0)
    assert not np.array_equal(out, base)
    for c in range(3):
        assert not np.array_equal(out[:, :, c], base[:, :, c])


def test_unsharp_g_only_green_channel(sample_bgr: np.ndarray) -> None:
    base = sample_bgr.copy()
    out = unsharp_masking(base, channels="G", threshold=0)
    assert np.array_equal(out[:, :, 0], base[:, :, 0])
    assert np.array_equal(out[:, :, 2], base[:, :, 2])
    assert not np.array_equal(out[:, :, 1], base[:, :, 1])


def test_center_crop_preserves_square_for_non_square(sample_bgr: np.ndarray) -> None:
    assert sample_bgr.shape[0] != sample_bgr.shape[1]
    cropped = center_crop_square(sample_bgr)
    assert cropped.shape[0] == cropped.shape[1] == min(sample_bgr.shape[:2])


def test_dcp_option_runs(sample_bgr: np.ndarray) -> None:
    default = enhance_fundus(sample_bgr, use_dcp=False, size=224)
    with_dcp = enhance_fundus(sample_bgr, use_dcp=True, size=224)
    assert with_dcp.shape == (224, 224, 3)
    assert float(with_dcp.mean()) != pytest.approx(float(default.mean()), abs=0.01)


def test_invalid_shape_raises() -> None:
    with pytest.raises(ValueError):
        enhance_fundus(np.zeros((10, 10), dtype=np.uint8), size=224)
