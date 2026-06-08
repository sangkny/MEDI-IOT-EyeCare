#!/usr/bin/env python3
"""v10 MultiTaskV10Model → ONNX (5-head 출력)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import torch
import torch.nn as nn

from training.train_v10 import MultiTaskV10Model


class V10OnnxWrapper(nn.Module):
    def __init__(self, model: MultiTaskV10Model) -> None:
        super().__init__()
        self.model = model

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, ...]:
        out = self.model.forward(x)
        return (
            out["dr"],
            out["glaucoma"],
            out["amd"],
            out["myopia"],
            out["multidisease"],
        )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--checkpoint", type=Path, default=ROOT / "models/retinal_v10/best.pt")
    p.add_argument("--output", type=Path, default=ROOT / "models/retinal_v10.onnx")
    p.add_argument("--meta-output", type=Path, default=ROOT / "models/retinal_v10.meta.json")
    args = p.parse_args()

    ckpt_path = args.checkpoint if args.checkpoint.is_absolute() else ROOT / args.checkpoint
    if not ckpt_path.is_file():
        raise SystemExit(f"checkpoint not found: {ckpt_path}")

    raw = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    state = raw.get("model_state") if isinstance(raw, dict) else raw

    model = MultiTaskV10Model(pretrained_imagenet=False)
    model.load_state_dict(state)
    model.eval()
    wrapper = V10OnnxWrapper(model)

    dummy = torch.randn(1, 3, 224, 224)
    out_path = args.output if args.output.is_absolute() else ROOT / args.output
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

    meta_src = ckpt_path.parent / "best.meta.json"
    meta_out = args.meta_output if args.meta_output.is_absolute() else ROOT / args.meta_output
    if meta_src.is_file():
        meta = json.loads(meta_src.read_text(encoding="utf-8"))
    else:
        meta = {}
    meta.update(
        {
            "arch": "efficientnet_b4_v10",
            "preprocess": "none",
            "image_size": 224,
            "outputs": ["dr", "glaucoma", "amd", "myopia", "multidisease"],
        }
    )
    meta_out.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"OK {meta_out}")


if __name__ == "__main__":
    main()
