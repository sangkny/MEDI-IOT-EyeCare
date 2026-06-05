#!/usr/bin/env python3
"""retinal_glaucoma_v2 best.pt → ONNX + meta.json."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import torch

from training.train_glaucoma import GlaucomaClassifier


def main() -> None:
    p = argparse.ArgumentParser(description="Export glaucoma v2 to ONNX")
    p.add_argument(
        "--checkpoint",
        type=Path,
        default=ROOT / "models" / "retinal_glaucoma_v2" / "best.pt",
    )
    p.add_argument("--output", type=Path, default=ROOT / "models" / "retinal_glaucoma_v2.onnx")
    p.add_argument("--meta", type=Path, default=None)
    p.add_argument("--image-size", dest="image_size", type=int, default=224)
    args = p.parse_args()

    ckpt_path = args.checkpoint if args.checkpoint.is_absolute() else ROOT / args.checkpoint
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    state = ckpt.get("model_state") or ckpt.get("state_dict") or ckpt

    model = GlaucomaClassifier(pretrained_imagenet=False)
    model.load_state_dict(state, strict=False)
    model.eval()

    meta_src = ckpt_path.parent / "best.meta.json"
    src_meta = {}
    if meta_src.is_file():
        src_meta = json.loads(meta_src.read_text(encoding="utf-8"))

    out = args.output if args.output.is_absolute() else ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)

    dummy = torch.randn(1, 3, args.image_size, args.image_size)
    torch.onnx.export(
        model,
        dummy,
        str(out),
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={"input": {0: "batch"}, "output": {0: "batch"}},
        opset_version=17,
    )

    meta_path = args.meta or out.with_name(out.stem + ".meta.json")
    if not meta_path.is_absolute():
        meta_path = ROOT / meta_path

    meta = {
        "arch": "efficientnet_b4_glaucoma",
        "task": "glaucoma",
        "preprocess": src_meta.get("preprocess") or "clahe",
        "image_size": args.image_size,
        "onnx": out.name,
        "source_checkpoint": ckpt_path.name,
        "best_val_auc": src_meta.get("best_val_auc") or ckpt.get("best_val_auc"),
        "test_auc": src_meta.get("test_auc") or ckpt.get("test_auc"),
        "version": "glaucoma_v2",
    }
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK {out} auc={meta.get('best_val_auc')} meta={meta_path}")


if __name__ == "__main__":
    main()
