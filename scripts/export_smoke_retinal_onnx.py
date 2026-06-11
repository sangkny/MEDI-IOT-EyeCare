#!/usr/bin/env python3
"""
파일명: export_smoke_retinal_onnx.py
목적: export_smoke_retinal_onnx.py 실행 스크립트
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가

스모크용 DR 분류기 ONNX export (학습 없이 구조만).

사용:
  python3 scripts/export_smoke_retinal_onnx.py

출력:
  models/retinal_v1.onnx
  models/retinal_v1.meta.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import torch  # noqa: E402

from services.retinal_cnn import DR_NUM_CLASSES, build_model  # noqa: E402


def main() -> None:
    arch = (sys.argv[1] if len(sys.argv) > 1 else "efficientnet_b4").strip()
    out_onnx = ROOT / "models" / "retinal_v1.onnx"
    out_meta = ROOT / "models" / "retinal_v1.meta.json"
    out_onnx.parent.mkdir(parents=True, exist_ok=True)

    model, resolved = build_model(arch, num_classes=DR_NUM_CLASSES)
    model.eval()

    dummy = torch.randn(1, 3, 224, 224)
    torch.onnx.export(
        model,
        dummy,
        str(out_onnx),
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={"input": {0: "batch"}},
        opset_version=17,
    )

    meta = {
        "arch": resolved,
        "num_classes": DR_NUM_CLASSES,
        "classes": [
            "No DR",
            "Mild DR",
            "Moderate DR",
            "Severe DR",
            "Proliferative DR",
        ],
        "image_size": 224,
        "input_size": [224, 224],
        "preprocess": "clahe",
        "version": "smoke-export",
    }
    out_meta.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print("OK", out_onnx, out_meta)


if __name__ == "__main__":
    main()
