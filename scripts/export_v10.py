#!/usr/bin/env python3
"""
파일명: export_v10.py
목적: v10c 5-head ONNX export (export_multidisease_v1.py 대체 금지)
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가

v10 / v10c MultiTaskV10Model → ONNX (5-head: dr·glaucoma·amd·myopia·multidisease).

export_multidisease_v1.py 는 출력 1개 — v10에 사용 금지.

예 (GPU):
  python3 scripts/export_v10.py \\
    --checkpoint models/retinal_v10c/best.pt \\
    --output models/retinal_v10c.onnx
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import torch
import torch.nn as nn

from training.make_manifest import MULTIDISEASE_TRAIN_CLASSES
from training.train_v10 import MultiTaskV10Model


class V10OnnxWrapper(nn.Module):
    """5-head logits → ONNX 친화 확률/로짓 텐서."""

    def __init__(self, model: MultiTaskV10Model) -> None:
        super().__init__()
        self.model = model

    def forward(
        self,
        x: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        out = self.model.forward(x)
        dr = torch.softmax(out["dr"], dim=-1)
        gl = torch.sigmoid(out["glaucoma"]).unsqueeze(-1)
        amd = torch.sigmoid(out["amd"]).unsqueeze(-1)
        myo = torch.sigmoid(out["myopia"]).unsqueeze(-1)
        multi = torch.sigmoid(out["multidisease"])
        return dr, gl, amd, myo, multi


def _load_state(ckpt_path: Path) -> dict:
    raw = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    if isinstance(raw, dict):
        state = raw.get("model_state") or raw.get("state_dict")
        if isinstance(state, dict):
            return state
    if isinstance(raw, dict):
        return raw
    raise SystemExit(f"invalid checkpoint: {ckpt_path}")


def _verify_onnx(onnx_path: Path, image_size: int = 224) -> None:
    import numpy as np
    import onnxruntime as ort

    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    inp = sess.get_inputs()[0].name
    dummy = np.random.randn(1, 3, image_size, image_size).astype(np.float32)
    outs = sess.run(None, {inp: dummy})
    print(f"출력 수: {len(outs)}")
    for i, arr in enumerate(outs):
        print(f"  [{i}] shape={arr.shape}")
    if len(outs) != 5:
        raise SystemExit(f"FAIL: expected 5 outputs, got {len(outs)}")


def main() -> None:
    p = argparse.ArgumentParser(description="Export v10 5-head ONNX")
    p.add_argument("--checkpoint", type=Path, required=True, help="best.pt path")
    p.add_argument("--output", type=Path, required=True, help=".onnx output path")
    p.add_argument(
        "--meta-output",
        type=Path,
        default=None,
        help="meta.json (default: <output_stem>.meta.json)",
    )
    p.add_argument("--image-size", dest="image_size", type=int, default=224)
    p.add_argument("--no-verify", action="store_true", help="skip onnxruntime shape check")
    args = p.parse_args()

    ckpt_path = args.checkpoint if args.checkpoint.is_absolute() else ROOT / args.checkpoint
    if not ckpt_path.is_file():
        raise SystemExit(f"checkpoint not found: {ckpt_path}")

    out_path = args.output if args.output.is_absolute() else ROOT / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)

    model = MultiTaskV10Model(pretrained_imagenet=False)
    model.load_state_dict(_load_state(ckpt_path), strict=False)
    model.eval()
    wrapper = V10OnnxWrapper(model)

    dummy = torch.randn(1, 3, args.image_size, args.image_size)
    torch.onnx.export(
        wrapper,
        dummy,
        str(out_path),
        input_names=["image"],
        output_names=["dr", "glaucoma", "amd", "myopia", "multidisease"],
        opset_version=17,
        dynamic_axes={"image": {0: "batch"}},
    )
    print(f"OK {out_path}")

    meta_out = args.meta_output
    if meta_out is None:
        meta_out = out_path.with_name(out_path.stem + ".meta.json")
    elif not meta_out.is_absolute():
        meta_out = ROOT / meta_out

    meta_src = ckpt_path.parent / "best.meta.json"
    meta: dict = {}
    if meta_src.is_file():
        meta = json.loads(meta_src.read_text(encoding="utf-8"))

    meta.update(
        {
            "arch": "efficientnet_b4_v10",
            "preprocess": meta.get("preprocess") or "none",
            "image_size": args.image_size,
            "outputs": ["dr", "glaucoma", "amd", "myopia", "multidisease"],
            "output_activations": {
                "dr": "softmax",
                "glaucoma": "sigmoid",
                "amd": "sigmoid",
                "myopia": "sigmoid",
                "multidisease": "sigmoid",
            },
            "label_classes": list(meta.get("label_classes") or MULTIDISEASE_TRAIN_CLASSES),
            "onnx": out_path.name,
            "source_checkpoint": ckpt_path.name,
        }
    )
    meta_out.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK {meta_out}")

    if not args.no_verify:
        _verify_onnx(out_path, image_size=args.image_size)


if __name__ == "__main__":
    main()
