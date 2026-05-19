#!/usr/bin/env python3
"""Retinal DR CNN 학습 + ONNX export (D R4-ML D2).

기본 백본: EfficientNet-B4 (``--arch efficientnet_b0|b4|v2_s``).

스모크 (합성 데이터, LM Studio·Messidor 불필요):

  pip install -r requirements-ml.txt
  python scripts/train_retinal.py --smoke --epochs 2

실데이터 (manifest D1):

  python scripts/train_retinal.py \\
    --manifest datasets/messidor2/manifest.json \\
    --epochs 5 --batch-size 16

산출: ``models/retinal_v1.pt``, ``models/retinal_v1.onnx``
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from services.retinal_cnn import (  # noqa: E402
    DEFAULT_CNN_ARCH,
    DEFAULT_IMAGE_SIZE,
    DR_NUM_CLASSES,
    build_dr_classifier,
    load_image_tensor_from_path,
    load_manifest_entries,
    resolve_cnn_arch,
    resolve_preprocess_mode,
)
from services.retinal_foundation import maybe_warn_foundation_skip  # noqa: E402


def _export_onnx(model, out_path: Path, image_size: int) -> None:
    import torch

    model.eval()
    dummy = torch.randn(1, 3, image_size, image_size)
    torch.onnx.export(
        model,
        dummy,
        str(out_path),
        input_names=["input"],
        output_names=["logits"],
        dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}},
        opset_version=17,
    )


def _synthetic_loader(n: int, batch_size: int, image_size: int):
    import torch
    from torch.utils.data import DataLoader, TensorDataset

    x = torch.randn(n, 3, image_size, image_size)
    y = torch.randint(0, DR_NUM_CLASSES, (n,))
    ds = TensorDataset(x, y)
    return DataLoader(ds, batch_size=batch_size, shuffle=True)


def _manifest_loader(
    manifest_path: Path,
    split: str,
    batch_size: int,
    image_size: int,
    preprocess_mode: str,
):
    import torch
    from torch.utils.data import DataLoader, Dataset

    entries = load_manifest_entries(manifest_path, split)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data_dir = Path(data["data_dir"])
    if not data_dir.is_absolute():
        data_dir = manifest_path.parent / data_dir

    class _DS(Dataset):
        def __len__(self) -> int:
            return len(entries)

        def __getitem__(self, idx: int):
            e = entries[idx]
            path = data_dir / e["path"]
            if path.is_file():
                t = load_image_tensor_from_path(
                    path,
                    image_size=image_size,
                    preprocess_mode=preprocess_mode,
                )[0]
            else:
                t = torch.randn(3, image_size, image_size)
            return t, int(e["dr_grade"])

    return DataLoader(_DS(), batch_size=batch_size, shuffle=True)


def train_and_export(args: argparse.Namespace) -> int:
    import torch
    import torch.nn as nn

    out_dir = Path(args.output_dir)
    if not out_dir.is_absolute():
        out_dir = _REPO / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    pt_path = out_dir / "retinal_v1.pt"
    onnx_path = out_dir / "retinal_v1.onnx"

    maybe_warn_foundation_skip()
    arch_key = resolve_cnn_arch(args.arch)
    preprocess = resolve_preprocess_mode(args.preprocess)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, arch_key = build_dr_classifier(arch=arch_key, pretrained=not args.smoke)
    model = model.to(device)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    loss_fn = nn.CrossEntropyLoss()

    if args.smoke:
        loader = _synthetic_loader(args.synthetic_samples, args.batch_size, args.image_size)
    else:
        manifest = Path(args.manifest).expanduser()
        if not manifest.is_absolute():
            manifest = _REPO / manifest
        loader = _manifest_loader(
            manifest, args.split, args.batch_size, args.image_size, preprocess
        )

    model.train()
    for epoch in range(args.epochs):
        total_loss = 0.0
        n_batches = 0
        for xb, yb in loader:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad()
            logits = model(xb)
            loss = loss_fn(logits, yb)
            loss.backward()
            opt.step()
            total_loss += float(loss.item())
            n_batches += 1
        print(f"[train_retinal] epoch {epoch + 1}/{args.epochs} loss={total_loss / max(n_batches, 1):.4f}")

    torch.save(
        {
            "state_dict": model.state_dict(),
            "arch": arch_key,
            "num_classes": DR_NUM_CLASSES,
            "image_size": args.image_size,
            "preprocess": preprocess,
            "smoke": bool(args.smoke),
        },
        pt_path,
    )
    _export_onnx(model.cpu(), onnx_path, args.image_size)
    meta = {
        "pt": str(pt_path),
        "onnx": str(onnx_path),
        "arch": arch_key,
        "num_classes": DR_NUM_CLASSES,
        "image_size": args.image_size,
        "preprocess": preprocess,
        "smoke": bool(args.smoke),
    }
    (out_dir / "retinal_v1.meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    print(f"[train_retinal] saved {pt_path} and {onnx_path}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Train retinal DR CNN (D R4-ML D2)")
    p.add_argument("--smoke", action="store_true", help="synthetic data, no manifest")
    p.add_argument("--manifest", default="datasets/messidor2/manifest.json")
    p.add_argument("--split", default="train", choices=["train", "val"])
    p.add_argument("--output-dir", default="models")
    p.add_argument("--epochs", type=int, default=5)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--image-size", type=int, default=DEFAULT_IMAGE_SIZE)
    p.add_argument(
        "--arch",
        default=DEFAULT_CNN_ARCH,
        help="efficientnet_b0 | efficientnet_b4 | efficientnet_v2_s | msef_net",
    )
    p.add_argument(
        "--preprocess",
        default=None,
        help="none | clahe | ben_graham | both (default: clahe)",
    )
    p.add_argument("--synthetic-samples", type=int, default=64)
    args = p.parse_args()

    try:
        return train_and_export(args)
    except ImportError as e:
        print(f"[train_retinal] missing dependency: {e}", file=sys.stderr)
        print("  pip install -r requirements-ml.txt", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
