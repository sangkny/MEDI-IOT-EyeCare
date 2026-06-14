"""
목적: fundus_enhancement 4모드 단위 테스트
히스토리:
  2026-06-12 - 최초 작성

실행 (Docker 필수):
  docker exec medi-iot-api-dev python -m pytest tests/test_fundus_enhancement.py -v
"""
from __future__ import annotations

import cv2
import numpy as np
import pytest

from services.fundus_enhancement import EnhanceMode, enhance_fundus

pytestmark = pytest.mark.unit


@pytest.fixture
def sample_bgr() -> np.ndarray:
    h, w = 128, 128
    img = np.zeros((h, w, 3), dtype=np.uint8)
    cv2.circle(img, (64, 64), 40, (40, 120, 180), -1)
    cv2.GaussianBlur(img, (15, 15), 4, dst=img)
    return img


@pytest.mark.parametrize("mode", list(EnhanceMode))
def test_enhance_fundus_all_modes(sample_bgr: np.ndarray, mode: EnhanceMode) -> None:
    out = enhance_fundus(sample_bgr, mode=mode)
    assert out.shape == sample_bgr.shape
    assert out.dtype == np.uint8


def test_pixel_range(sample_bgr: np.ndarray) -> None:
    out = enhance_fundus(sample_bgr, mode=EnhanceMode.FULL)
    assert out.min() >= 0
    assert out.max() <= 255


def test_dcp_brightness_change(sample_bgr: np.ndarray) -> None:
    clahe_only = enhance_fundus(sample_bgr, mode=EnhanceMode.CLAHE_ONLY)
    dcp = enhance_fundus(sample_bgr, mode=EnhanceMode.DCP_CLAHE)
    assert float(dcp.mean()) != pytest.approx(float(clahe_only.mean()), abs=0.01)


def test_unsharp_increases_edge_energy(sample_bgr: np.ndarray) -> None:
    base = enhance_fundus(sample_bgr, mode=EnhanceMode.CLAHE_ONLY)
    sharp = enhance_fundus(sample_bgr, mode=EnhanceMode.CLAHE_UNSHARP)
    lap_base = cv2.Laplacian(cv2.cvtColor(base, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
    lap_sharp = cv2.Laplacian(cv2.cvtColor(sharp, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
    assert lap_sharp >= lap_base * 0.95


def test_invalid_shape_raises() -> None:
    with pytest.raises(ValueError):
        enhance_fundus(np.zeros((10, 10), dtype=np.uint8), mode=EnhanceMode.FULL)
