#!/usr/bin/env python3
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from korean_gl_crop_utils import (
    _gradient_sum,
    _merge_close_boundaries,
    detect_boundaries,
    detect_boundaries_by_gradient,
)

INPUT = Path("/dataset/korean_fundus_input/glaucoma_modified")

for n in [1, 3, 6, 19]:
    img = cv2.imread(str(INPUT / f"{n}.jpg"))
    sr, _ = detect_boundaries(img)
    bottom = img[sr:, :, :]
    raw = detect_boundaries_by_gradient(bottom)
    merged = _merge_close_boundaries(bottom, raw)
    gs = _gradient_sum(bottom)
    print(f"No.{n} raw={raw} merged={merged}")
    for b in merged:
        print(f"  col={b} score={gs[b]:.1f} ratio={gs[b] / max(gs.mean(), 1e-6):.1f}x")
