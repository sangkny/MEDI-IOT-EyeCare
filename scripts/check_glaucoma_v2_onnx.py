#!/usr/bin/env python3
"""glaucoma_v2 ONNX 입출력 shape 확인 (Option 3 가능 여부)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import onnxruntime as ort

CANDIDATES = [
    ROOT / "models/retinal_glaucoma_v2.onnx",
    ROOT / "models/retinal_glaucoma_v2/model.onnx",
    ROOT / "models/glaucoma_v2.onnx",
]


def main() -> None:
    path = next((p for p in CANDIDATES if p.is_file()), None)
    if path is None:
        print("FAIL: glaucoma_v2 ONNX not found")
        for p in CANDIDATES:
            print(f"  tried {p}")
        sys.exit(1)
    print(f"path: {path}")
    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    print("inputs:", [(i.name, i.shape, i.type) for i in sess.get_inputs()])
    print("outputs:", [(o.name, o.shape, o.type) for o in sess.get_outputs()])
    out_shapes = [list(o.shape) for o in sess.get_outputs()]
    if any(len(s) >= 3 and s[1] in (2, 3) for s in out_shapes):
        print("Option 3: POSSIBLE (segmentation output detected)")
    else:
        print("Option 3: NOT AVAILABLE (classification-only)")


if __name__ == "__main__":
    main()
