"""
파일명: fundus_enhancement.py
목적: 안저 이미지 고품질 전처리 파이프라인
      CLAHE + Dark Channel Prior Dehazing + Unsharp Masking
논문 근거:
  - IETK-Ret: Enhancement of Retinal Fundus Images via
    Pixel Color Amplification (MICCAI 2020)
    → Dice score +0.491 향상 입증
  - Dark Channel Prior (He et al. 2009): dehazing SOTA
히스토리:
  2026-06-12 - 최초 작성
"""
from __future__ import annotations

from enum import Enum

import cv2
import numpy as np


class EnhanceMode(str, Enum):
    CLAHE_ONLY = "clahe"
    CLAHE_UNSHARP = "clahe_unsharp"
    DCP_CLAHE = "dcp_clahe"
    FULL = "full"


def dark_channel_prior_dehaze(
    img: np.ndarray,
    *,
    patch_size: int = 15,
    omega: float = 0.95,
    t0: float = 0.1,
) -> np.ndarray:
    """
    Dark Channel Prior 기반 안저 이미지 dehazing.
    뿌연/흐릿한 안저 이미지 개선 — 백내장 환자 이미지에 특히 효과적.
    """
    img_f = img.astype(np.float64) / 255.0
    dark = np.min(img_f, axis=2)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (patch_size, patch_size))
    dark_channel = cv2.erode(dark, kernel)
    num_pixels = dark_channel.size
    num_brightest = max(int(num_pixels * 0.001), 1)
    flat = dark_channel.flatten()
    indices = np.argsort(flat)[-num_brightest:]
    rows = indices // img_f.shape[1]
    cols = indices % img_f.shape[1]
    a = np.max(img_f[rows, cols], axis=0)
    a = np.clip(a, 0.1, 1.0)
    norm = img_f / a[np.newaxis, np.newaxis, :]
    t = 1.0 - omega * np.min(norm, axis=2)
    t = np.maximum(t, t0)
    t3 = t[:, :, np.newaxis]
    recovered = (img_f - a) / t3 + a
    return np.clip(recovered * 255, 0, 255).astype(np.uint8)


def unsharp_masking(
    img: np.ndarray,
    *,
    sigma: float = 1.0,
    strength: float = 1.2,
    threshold: int = 0,
) -> np.ndarray:
    """Unsharp Masking — 혈관/시신경 경계 강조."""
    blurred = cv2.GaussianBlur(img, (0, 0), sigma)
    if threshold > 0:
        mask = cv2.subtract(img, blurred)
        low_contrast = np.abs(mask) < threshold
        sharpened = cv2.addWeighted(img, 1.0 + strength, blurred, -strength, 0)
        sharpened[low_contrast] = img[low_contrast]
    else:
        sharpened = cv2.addWeighted(img, 1.0 + strength, blurred, -strength, 0)
    return np.clip(sharpened, 0, 255).astype(np.uint8)


def apply_clahe_bgr(
    img: np.ndarray,
    *,
    clahe_clip: float = 2.0,
    clahe_grid: tuple[int, int] = (8, 8),
) -> np.ndarray:
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    clahe = cv2.createCLAHE(clipLimit=clahe_clip, tileGridSize=clahe_grid)
    lab[:, :, 0] = clahe.apply(lab[:, :, 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def enhance_fundus(
    img: np.ndarray,
    mode: EnhanceMode | str = EnhanceMode.FULL,
    *,
    clahe_clip: float = 2.0,
    clahe_grid: tuple[int, int] = (8, 8),
    unsharp_sigma: float = 1.0,
    unsharp_strength: float = 1.2,
) -> np.ndarray:
    """
    안저 이미지 통합 전처리 파이프라인.
    Step 1: DCP Dehazing (뿌연 제거)
    Step 2: CLAHE (국소 대비)
    Step 3: Unsharp (경계 강조)
    """
    if isinstance(mode, str):
        mode = EnhanceMode(mode)
    if img.ndim != 3 or img.shape[2] != 3:
        raise ValueError(f"expected H×W×3 BGR image, got shape={img.shape}")

    result = img.copy()
    if mode in (EnhanceMode.DCP_CLAHE, EnhanceMode.FULL):
        result = dark_channel_prior_dehaze(result)

    if mode in (
        EnhanceMode.CLAHE_ONLY,
        EnhanceMode.CLAHE_UNSHARP,
        EnhanceMode.DCP_CLAHE,
        EnhanceMode.FULL,
    ):
        result = apply_clahe_bgr(
            result, clahe_clip=clahe_clip, clahe_grid=clahe_grid
        )

    if mode in (EnhanceMode.CLAHE_UNSHARP, EnhanceMode.FULL):
        result = unsharp_masking(
            result, sigma=unsharp_sigma, strength=unsharp_strength
        )
    return result
