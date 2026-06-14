#!/usr/bin/env python3
"""
파일명: compare_v2.py
목적: v1(직접 resize) vs v2(CenterCrop+CLAHE+Unsharp) 시각 비교
실행: Docker 컨테이너 내부에서만 실행
히스토리:
  2026-06-13 - 최초 작성

개발 PC:
  docker exec medi-iot-api-dev python3 scripts/compare_v2.py \\
    --image fundus_right_sklee.jpg \\
    --output /tmp/compare_v2.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from services.fundus_enhancement import clahe_apply, enhance_fundus  # noqa: E402

IMAGE_SIZE = 224


def v1_pipeline(img_bgr: np.ndarray) -> np.ndarray:
    """v1: CLAHE → 직접 resize (원형 왜곡)."""
    out = clahe_apply(img_bgr)
    return cv2.resize(out, (IMAGE_SIZE, IMAGE_SIZE), interpolation=cv2.INTER_LANCZOS4)


def v2_pipeline(img_bgr: np.ndarray) -> np.ndarray:
    """v2: CenterCrop + CLAHE + Unsharp(RGB)."""
    return enhance_fundus(img_bgr, size=IMAGE_SIZE)


def _label_panel(img: np.ndarray, text: str) -> np.ndarray:
    panel = img.copy()
    cv2.rectangle(panel, (0, 0), (panel.shape[1], 28), (15, 23, 42), -1)
    cv2.putText(
        panel,
        text,
        (8, 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (226, 232, 240),
        1,
        cv2.LINE_AA,
    )
    return panel


def build_comparison(img_bgr: np.ndarray, target_h: int = 256) -> np.ndarray:
    panels = [
        (v1_pipeline(img_bgr), "v1: CLAHE + direct resize (distortion)"),
        (v2_pipeline(img_bgr), "v2: CLAHE + Unsharp(RGB) + CenterCrop"),
    ]
    out_panels: list[np.ndarray] = []
    for img, label in panels:
        scale = target_h / img.shape[0]
        w = int(img.shape[1] * scale)
        resized = cv2.resize(img, (w, target_h), interpolation=cv2.INTER_AREA)
        out_panels.append(_label_panel(resized, label))
    return np.vstack(out_panels)


def main() -> None:
    p = argparse.ArgumentParser(description="Compare v1 vs v2 fundus preprocessing")
    p.add_argument("--image", type=Path, required=True)
    p.add_argument("--output", type=Path, default=ROOT / "compare_v2.png")
    p.add_argument("--height", type=int, default=256)
    args = p.parse_args()

    img_path = args.image if args.image.is_absolute() else ROOT / args.image
    img = cv2.imread(str(img_path))
    if img is None:
        raise SystemExit(f"FAIL: cannot read {img_path}")

    collage = build_comparison(img, target_h=args.height)
    out = args.output if args.output.is_absolute() else ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), collage)
    print(f"OK → {out} ({collage.shape[1]}x{collage.shape[0]})")


if __name__ == "__main__":
    main()
