#!/usr/bin/env python3
"""
파일명: compare_enhancement.py
목적: 4가지 전처리 모드 시각 비교 (CLAHE / CLAHE+Unsharp / DCP+CLAHE / FULL)
실행: Docker 컨테이너 내부에서만 실행
히스토리:
  2026-06-12 - 최초 작성

개발 PC:
  docker exec medi-iot-api-dev python3 scripts/compare_enhancement.py \\
    --image /app/fundus_right_sklee.jpg \\
    --output /app/enhancement_comparison.png

GPU:
  docker run --rm -v $REPO:/workspace medi-train:gpu \\
    bash -c 'python3 /workspace/scripts/compare_enhancement.py \\
      --image /workspace/fundus_right_sklee.jpg \\
      --output /workspace/enhancement_comparison.png'
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from services.fundus_enhancement import EnhanceMode, enhance_fundus  # noqa: E402

MODES = [
    (EnhanceMode.CLAHE_ONLY, "CLAHE only"),
    (EnhanceMode.CLAHE_UNSHARP, "CLAHE+Unsharp"),
    (EnhanceMode.DCP_CLAHE, "DCP+CLAHE"),
    (EnhanceMode.FULL, "FULL"),
]


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


def build_comparison(img_bgr: np.ndarray, target_h: int = 512) -> np.ndarray:
    panels: list[np.ndarray] = []
    for mode, label in MODES:
        out = enhance_fundus(img_bgr, mode=mode)
        scale = target_h / out.shape[0]
        w = int(out.shape[1] * scale)
        resized = cv2.resize(out, (w, target_h), interpolation=cv2.INTER_AREA)
        panels.append(_label_panel(resized, label))
    return np.vstack(panels)


def main() -> None:
    p = argparse.ArgumentParser(description="Compare fundus enhancement modes")
    p.add_argument("--image", type=Path, required=True)
    p.add_argument("--output", type=Path, default=ROOT / "enhancement_comparison.png")
    p.add_argument("--height", type=int, default=512)
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
