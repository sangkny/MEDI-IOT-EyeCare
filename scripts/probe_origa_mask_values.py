#!/usr/bin/env python3
"""ORIGA Masks_Square 픽셀 인코딩 확인."""
import cv2
import numpy as np
from pathlib import Path

root = Path("/dataset/Glaucoma_raw/ORIGA/Masks_Square")
for name in ("001.png", "100.png", "360.png"):
    p = root / name
    if not p.is_file():
        print(name, "missing")
        continue
    m = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)
    print(name, "shape", m.shape, "unique", np.unique(m)[:20], "n", len(np.unique(m)))
