#!/usr/bin/env python3
"""gradient 크롭 레이아웃 단위 테스트 — No.1, 3, 6, 19."""
from __future__ import annotations

import sys
from pathlib import Path

import cv2

_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))
from korean_gl_crop_utils import analyze_bottom_layout, detect_boundaries_by_gradient

INPUT = Path("/dataset/korean_fundus_input/glaucoma_modified")
SAMPLES = [1, 3, 6, 19]


def main() -> None:
    print("=== gradient layout unit test ===")
    for n in SAMPLES:
        path = INPUT / f"{n}.jpg"
        img = cv2.imread(str(path))
        if img is None:
            print(f"  No.{n}: FAIL load {path}")
            continue
        h, w = img.shape[:2]
        split_row, split_col = __import__(
            "korean_gl_crop_utils", fromlist=["detect_boundaries"]
        ).detect_boundaries(img)
        bottom = img[split_row:, :, :]
        bounds = detect_boundaries_by_gradient(bottom)
        layout = analyze_bottom_layout(img)
        expected = {1: "2split", 3: "2split", 6: "4split", 19: "2split"}
        ok = "OK" if layout["layout"] == expected.get(n) else f"FAIL want {expected.get(n)}"
        grad_max = 0.0
        diff = __import__("numpy").abs(
            __import__("numpy").diff(bottom.astype(float), axis=1)
        )
        gs = diff.mean(axis=2).sum(axis=0)
        if len(gs):
            grad_max = float(gs.max() / max(gs.mean(), 1e-6))
        print(
            f"  No.{n}: {ok} size={w}x{h} layout={layout['layout']} "
            f"boundaries={layout['bottom_splits']} "
            f"peak_ratio~{grad_max:.1f}x "
            f"od={layout.get('od_box')} os={layout.get('os_box')}"
        )


if __name__ == "__main__":
    main()
