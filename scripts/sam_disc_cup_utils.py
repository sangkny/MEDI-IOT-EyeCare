#!/usr/bin/env python3
"""Disc/Cup SAM pseudo-mask 공통 유틸 (generate · evaluate 공유)."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

MASK_BG = 0
MASK_DISC = 1
MASK_CUP = 2
DEFAULT_SIZE = 224


def center_crop_square_2d(mask: np.ndarray) -> np.ndarray:
    h, w = mask.shape[:2]
    size = min(h, w)
    y0 = (h - size) // 2
    x0 = (w - size) // 2
    return mask[y0 : y0 + size, x0 : x0 + size].copy()


def resize_mask(mask: np.ndarray, size: int = DEFAULT_SIZE) -> np.ndarray:
    cropped = center_crop_square_2d(mask)
    if size > 0 and (cropped.shape[0] != size or cropped.shape[1] != size):
        cropped = cv2.resize(cropped, (size, size), interpolation=cv2.INTER_NEAREST)
    return cropped


def bbox_from_shapes(shapes: list[dict]) -> np.ndarray | None:
    """labelme shapes → SAM box prompt [x1,y1,x2,y2]."""
    for label in ("discloc", "disc"):
        for shape in shapes:
            if str(shape.get("label", "")).lower() != label:
                continue
            pts = shape.get("points") or []
            if len(pts) < 2:
                continue
            arr = np.array(pts, dtype=np.float32)
            x1, y1 = arr.min(axis=0)
            x2, y2 = arr.max(axis=0)
            if x2 > x1 and y2 > y1:
                return np.array([x1, y1, x2, y2], dtype=np.float32)
    return None


def bbox_from_discloc_json(json_path: Path) -> np.ndarray | None:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    return bbox_from_shapes(data.get("shapes") or [])


def estimate_disc_bbox(bgr: np.ndarray, *, radius_ratio: float = 0.18) -> np.ndarray:
    """밝기 기반 optic disc BBox 추정 (Phase 2)."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (31, 31), 0)
    h, w = gray.shape
    thresh = float(np.percentile(blurred, 98.5))
    bright = blurred >= thresh
    if bright.sum() < 16:
        cx, cy = w // 2, h // 2
    else:
        ys, xs = np.nonzero(bright)
        cx = int(np.mean(xs))
        cy = int(np.mean(ys))
    r = max(int(min(h, w) * radius_ratio), 12)
    x1 = max(cx - r, 0)
    y1 = max(cy - r, 0)
    x2 = min(cx + r, w - 1)
    y2 = min(cy + r, h - 1)
    return np.array([x1, y1, x2, y2], dtype=np.float32)


def cup_box_from_disc_box(disc_box: np.ndarray, *, scale: float = 0.55) -> np.ndarray:
    x1, y1, x2, y2 = disc_box
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    bw, bh = (x2 - x1) * scale, (y2 - y1) * scale
    return np.array([cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2], dtype=np.float32)


def combine_disc_cup_masks(disc_mask: np.ndarray, cup_mask: np.ndarray) -> np.ndarray:
    out = np.zeros_like(disc_mask, dtype=np.uint8)
    out[disc_mask.astype(bool)] = MASK_DISC
    out[cup_mask.astype(bool) & disc_mask.astype(bool)] = MASK_CUP
    return out


def dice_class(pred: np.ndarray, gt: np.ndarray, cls: int) -> float:
    p = pred == cls
    g = gt == cls
    inter = float((p & g).sum())
    denom = float(p.sum() + g.sum())
    if denom < 1.0:
        return 1.0 if inter < 1.0 else 0.0
    return 2.0 * inter / denom


def mean_disc_cup_dice(pred: np.ndarray, gt: np.ndarray) -> float:
    d1 = dice_class(pred, gt, MASK_DISC)
    d2 = dice_class(pred, gt, MASK_CUP)
    return (d1 + d2) / 2.0
