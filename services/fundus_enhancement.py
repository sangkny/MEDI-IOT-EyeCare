"""
파일명: services/fundus_enhancement.py
목적: 안저 이미지 전처리 v2
      CenterCrop + CLAHE + Unsharp(RGB/RG/G) + DCP(옵션)
교훈:
  v1 문제: 직접 resize → 안저 원형 왜곡 (CDR 비율 손상)
  v2 해결: CenterCrop(짧은 변 기준) → resize
  Unsharp: RGB 채널 기본 (혈관R + 조직G 동시 강조)
  DCP: 유두 국소 적용 (전체 적용 시 역효과)
  최적 파라미터: sigma=1.5, strength=1.8
히스토리:
  2026-06-12 - v1 최초 작성 (EnhanceMode, 전체 resize)
  2026-06-13 - v2 재작성 (CenterCrop, Unsharp RGB, DCP 국소)
"""
from __future__ import annotations

from typing import Literal

import cv2
import numpy as np

UnsharpChannels = Literal["RGB", "RG", "R", "G", "B"]

_CHANNEL_INDICES: dict[str, list[int]] = {
    "B": [0],
    "G": [1],
    "R": [2],
    "RG": [1, 2],
    "RGB": [0, 1, 2],
}


def _validate_bgr(img: np.ndarray) -> None:
    if img.ndim != 3 or img.shape[2] != 3:
        raise ValueError(f"expected H×W×3 BGR image, got shape={img.shape}")


def center_crop_square(img: np.ndarray) -> np.ndarray:
    """짧은 변 기준 중앙 정사각형 크롭."""
    _validate_bgr(img)
    h, w = img.shape[:2]
    size = min(h, w)
    y0 = (h - size) // 2
    x0 = (w - size) // 2
    return img[y0 : y0 + size, x0 : x0 + size].copy()


def clahe_apply(
    img: np.ndarray,
    *,
    clip: float = 2.0,
    grid: tuple[int, int] = (8, 8),
) -> np.ndarray:
    """LAB L-channel CLAHE (BGR 입력)."""
    _validate_bgr(img)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=grid)
    lab[:, :, 0] = clahe.apply(lab[:, :, 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def unsharp_masking(
    img: np.ndarray,
    *,
    sigma: float = 1.5,
    strength: float = 1.8,
    threshold: int = 5,
    channels: UnsharpChannels | str = "RGB",
) -> np.ndarray:
    """선택 채널 Unsharp Masking — 혈관(R)·조직(G) 경계 강조."""
    _validate_bgr(img)
    ch_key = str(channels).upper()
    if ch_key not in _CHANNEL_INDICES:
        raise ValueError(f"unknown channels={channels!r}, expected one of {_CHANNEL_INDICES}")
    active = _CHANNEL_INDICES[ch_key]
    out = img.astype(np.float32)
    for c in active:
        ch = img[:, :, c].astype(np.float32)
        blurred = cv2.GaussianBlur(ch, (0, 0), sigma)
        detail = ch - blurred
        if threshold > 0:
            mask = np.abs(detail) >= threshold
            sharpened = np.clip(ch + strength * detail, 0, 255)
            ch_out = np.where(mask, sharpened, ch)
        else:
            ch_out = cv2.addWeighted(ch, 1.0 + strength, blurred, -strength, 0)
        out[:, :, c] = ch_out
    return np.clip(out, 0, 255).astype(np.uint8)


def dcp_dehaze(
    img: np.ndarray,
    *,
    patch_size: int = 15,
    omega: float = 0.95,
    t0: float = 0.1,
) -> np.ndarray:
    """Dark Channel Prior — 전체 이미지 dehazing (He et al. 2009)."""
    _validate_bgr(img)
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


def local_disc_dcp(
    img: np.ndarray,
    *,
    disc_radius_ratio: float = 0.18,
    patch_size: int = 15,
    omega: float = 0.95,
    t0: float = 0.1,
) -> np.ndarray:
    """시신경 유두 중심 국소 DCP — 주변은 원본 유지."""
    _validate_bgr(img)
    dehazed = dcp_dehaze(img, patch_size=patch_size, omega=omega, t0=t0)
    h, w = img.shape[:2]
    cy, cx = h // 2, w // 2
    radius = max(int(min(h, w) * disc_radius_ratio), 8)
    mask = np.zeros((h, w), dtype=np.float32)
    cv2.circle(mask, (cx, cy), radius, 1.0, -1)
    mask = cv2.GaussianBlur(mask, (0, 0), radius * 0.35)
    mask3 = mask[:, :, np.newaxis]
    blended = dehazed.astype(np.float32) * mask3 + img.astype(np.float32) * (1.0 - mask3)
    return np.clip(blended, 0, 255).astype(np.uint8)


def enhance_fundus(
    img: np.ndarray,
    *,
    use_clahe: bool = True,
    use_unsharp: bool = True,
    use_dcp: bool = False,
    unsharp_channels: UnsharpChannels | str = "RGB",
    unsharp_sigma: float = 1.5,
    unsharp_strength: float = 1.8,
    size: int = 224,
) -> np.ndarray:
    """
    v2 통합 파이프라인.

    처리 순서: [local DCP] → CLAHE → Unsharp → CenterCrop → size×size resize
    """
    _validate_bgr(img)
    result = img.copy()
    if use_dcp:
        result = local_disc_dcp(result)
    if use_clahe:
        result = clahe_apply(result)
    if use_unsharp:
        result = unsharp_masking(
            result,
            sigma=unsharp_sigma,
            strength=unsharp_strength,
            channels=unsharp_channels,
        )
    cropped = center_crop_square(result)
    if size > 0 and (cropped.shape[0] != size or cropped.shape[1] != size):
        cropped = cv2.resize(cropped, (size, size), interpolation=cv2.INTER_LANCZOS4)
    return cropped
