#!/usr/bin/env python3
"""v9 multitask best.pt → DR 헤드만 추출 → retinal_v9_dr.onnx + meta.json."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import torch
import torch.nn as nn

from training.train_multitask import MultiTaskEyeCareModel


class DRHeadOnlyModel(nn.Module):
    """MultiTaskEyeCareModel DR 경로만 ONNX export."""

    def __init__(self, source: MultiTaskEyeCareModel) -> None:
        super().__init__()
        self.features = source.features
        self.avgpool = source.avgpool
        self.dropout = source.dropout
        self.dr_head = source.dr_head

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = self.avgpool(x)
        x = torch.flatten(x, 1)
        x = self.dropout(x)
        return self.dr_head(x)


def main() -> None:
    p = argparse.ArgumentParser(description="Export v9 DR head to ONNX")
    p.add_argument(
        "--checkpoint",
        type=Path,
        default=ROOT / "models" / "retinal_v9_multitask" / "best.pt",
    )
    p.add_argument("--output", type=Path, default=ROOT / "models" / "retinal_v9_dr.onnx")
    p.add_argument("--image-size", dest="image_size", type=int, default=224)
    args = p.parse_args()

    ckpt_path = args.checkpoint if args.checkpoint.is_absolute() else ROOT / args.checkpoint
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    state = ckpt.get("model_state") or ckpt.get("state_dict") or ckpt

    mt = MultiTaskEyeCareModel(pretrained_imagenet=False)
    mt.load_state_dict(state, strict=False)
    model = DRHeadOnlyModel(mt)
    model.eval()

    meta_src = ckpt_path.parent / "best.meta.json"
    src_meta = {}
    if meta_src.is_file():
        src_meta = json.loads(meta_src.read_text(encoding="utf-8"))

    out = args.output if args.output.is_absolute() else ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)

    dummy = torch.randn(1, 3, args.image_size, args.image_size)
    export_kw: dict = {
        "input_names": ["input"],
        "output_names": ["output"],
        "dynamic_axes": {"input": {0: "batch"}, "output": {0: "batch"}},
        "opset_version": 14,
    }
    try:
        torch.onnx.export(model, dummy, str(out), dynamo=False, **export_kw)
    except TypeError:
        torch.onnx.export(model, dummy, str(out), **export_kw)

    val_qwk = src_meta.get("best_val_qwk") or ckpt.get("best_val_qwk")
    meta = {
        "arch": "efficientnet_b4",
        "source": "retinal_v9_multitask",
        "source_checkpoint": ckpt_path.name,
        "preprocess": "clahe",
        "image_size": args.image_size,
        "onnx": out.name,
        "best_val_qwk": val_qwk,
        "baseline_v4_qwk": 0.8204,
        "version": "v9_dr_head",
        "note": "DR head only from v9 multitask; Glaucoma head excluded",
    }
    meta_path = out.with_name(out.stem + ".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK {out} qwk={val_qwk} meta={meta_path}")


if __name__ == "__main__":
    main()
