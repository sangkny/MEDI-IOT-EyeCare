#!/usr/bin/env python3
"""
파일명: export_onnx.py
목적: export_onnx.py 실행 스크립트
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가

학습된 .pt → ONNX + meta.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import torch

from services.retinal_cnn import build_dr_classifier


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--arch", default=None)
    p.add_argument("--output", type=Path, default=None)
    p.add_argument("--image-size", dest="image_size", type=int, default=224)
    args = p.parse_args()

    pt_path = args.model if args.model.is_absolute() else ROOT / args.model
    ckpt = torch.load(pt_path, map_location="cpu", weights_only=False)
    arch = args.arch or ckpt.get("arch") or "efficientnet_b4"
    image_size = int(ckpt.get("image_size") or args.image_size)
    preprocess = ckpt.get("preprocess") or "clahe"

    model, arch_key = build_dr_classifier(arch=arch, pretrained=False)
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    out = args.output or pt_path.with_suffix(".onnx")
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)

    dummy = torch.randn(1, 3, image_size, image_size)
    torch.onnx.export(
        model,
        dummy,
        str(out),
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={"input": {0: "batch"}, "output": {0: "batch"}},
        opset_version=17,
    )

    meta = {
        "arch": arch_key,
        "preprocess": preprocess,
        "image_size": image_size,
        "onnx": out.name,
        "pt": pt_path.name,
        "version": "export-v2",
        "qwk": ckpt.get("best_val_qwk"),
    }
    meta_path = out.with_name(out.stem + ".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK {out} {meta_path}")


if __name__ == "__main__":
    main()
