#!/usr/bin/env python3
"""retinal_myopia_v1 best.pt → ONNX + meta.json."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import torch

from training.train_myopia import MyopiaClassifier


def _map_state_for_export(state: dict) -> dict:
    out: dict = {}
    for k, v in state.items():
        key = k[7:] if k.startswith("module.") else k
        out[key] = v
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Export Myopia v1 to ONNX")
    p.add_argument(
        "--checkpoint",
        type=Path,
        default=ROOT / "models" / "retinal_myopia_v1" / "best.pt",
    )
    p.add_argument("--output", type=Path, default=ROOT / "models" / "retinal_myopia_v1.onnx")
    p.add_argument("--meta", type=Path, default=None)
    p.add_argument("--image-size", dest="image_size", type=int, default=224)
    args = p.parse_args()

    ckpt_path = args.checkpoint if args.checkpoint.is_absolute() else ROOT / args.checkpoint
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    state = ckpt.get("model_state") or ckpt.get("state_dict") or ckpt
    if not isinstance(state, dict):
        raise SystemExit(f"invalid checkpoint: {ckpt_path}")

    model = MyopiaClassifier(pretrained_imagenet=False)
    model.load_state_dict(_map_state_for_export(state), strict=False)
    model.eval()

    meta_src = ckpt_path.parent / "best.meta.json"
    src_meta: dict = {}
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
        "arch": "efficientnet_b4_myopia",
        "task": "myopia",
        "manifest": src_meta.get("manifest") or "myopia_v1.json",
        "preprocess": src_meta.get("preprocess") or "clahe",
        "image_size": args.image_size,
        "onnx": out.name,
        "source_checkpoint": ckpt_path.name,
        "pt": ckpt_path.name,
        "best_val_auc": src_meta.get("best_val_auc") or ckpt.get("best_val_auc"),
        "test_auc": src_meta.get("test_auc") or ckpt.get("test_auc"),
        "epochs": src_meta.get("epochs"),
        "focal_alpha": src_meta.get("focal_alpha"),
        "focal_gamma": src_meta.get("focal_gamma"),
        "version": "myopia_v1",
    }
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK {out} auc={meta.get('best_val_auc')} meta={meta_path}")


if __name__ == "__main__":
    main()
