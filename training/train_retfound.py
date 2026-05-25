#!/usr/bin/env python3
"""RETFound / ViT-Large 안저 DR 파인튜닝 (TITAN X 12GB, batch=4 권장).

사전학습 가중치 (1.7GB):
  wget -O models/RETFound_cfp.pth \\
    'https://huggingface.co/YangLabHKUST/RETFound_MAE/resolve/main/RETFound_cfp.pth'

예:
  python training/train_retfound.py \\
    --manifest training/manifests/unified_eyepacs.json \\
    --pretrained models/RETFound_cfp.pth \\
    --batch-size 4 --epochs 30 --lr 1e-6 \\
    --output models/retinal_v7_retfound.pt

체크포인트가 없으면 timm ``vit_large_patch16_224`` ImageNet 백본으로 스모크만 가능합니다.
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
from torch.utils.data import DataLoader

from training.train import (
    FundusManifestDataset,
    _class_weights,
    _sample_weights,
    evaluate_model,
    export_onnx,
)
from services.retinal_cnn import DR_NUM_CLASSES, resolve_preprocess_mode
from torch.utils.data import WeightedRandomSampler


def _build_vit_classifier(
    *,
    pretrained_path: Path | None,
    num_classes: int = DR_NUM_CLASSES,
) -> tuple[nn.Module, str]:
    import timm

    model = timm.create_model(
        "vit_large_patch16_224",
        pretrained=pretrained_path is None,
        num_classes=num_classes,
    )
    if pretrained_path and pretrained_path.is_file():
        state = torch.load(pretrained_path, map_location="cpu", weights_only=False)
        if isinstance(state, dict) and "model" in state:
            state = state["model"]
        missing, unexpected = model.load_state_dict(state, strict=False)
        print(
            f"RETFound weights: {pretrained_path.name} "
            f"missing={len(missing)} unexpected={len(unexpected)}"
        )
    return model, "vit_large_retfound"


def main() -> None:
    p = argparse.ArgumentParser(description="RETFound / ViT-Large DR fine-tune")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--pretrained", type=Path, default=None)
    p.add_argument("--epochs", type=int, default=30)
    p.add_argument("--batch-size", dest="batch_size", type=int, default=4)
    p.add_argument("--lr", type=float, default=1e-6)
    p.add_argument("--image-size", dest="image_size", type=int, default=224)
    p.add_argument("--preprocess", default="clahe")
    p.add_argument("--output", type=Path, default=ROOT / "models" / "retinal_v7_retfound.pt")
    p.add_argument("--device", default="cuda")
    p.add_argument("--early-stop", dest="early_stop", type=int, default=10)
    p.add_argument("--skip-onnx", action="store_true")
    args = p.parse_args()

    manifest_path = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data_dir = Path(data["data_dir"])
    if not data_dir.is_absolute():
        data_dir = ROOT / data_dir
    train_entries = data.get("train") or []
    val_entries = data.get("val") or []

    preprocess = resolve_preprocess_mode(args.preprocess)
    use_cuda = args.device == "cuda" and torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")

    train_ds = FundusManifestDataset(
        train_entries, data_dir, image_size=args.image_size, preprocess=preprocess, augment=True
    )
    val_ds = FundusManifestDataset(
        val_entries, data_dir, image_size=args.image_size, preprocess=preprocess, augment=False
    )
    sampler = WeightedRandomSampler(
        weights=_sample_weights(train_entries),
        num_samples=len(train_entries),
        replacement=True,
    )
    train_loader = DataLoader(
        train_ds, batch_size=args.batch_size, sampler=sampler, num_workers=0
    )
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=0)

    model, arch_key = _build_vit_classifier(pretrained_path=args.pretrained)
    model.to(device)
    loss_fn = nn.CrossEntropyLoss(weight=_class_weights(train_entries).to(device))
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)

    best_qwk = -1.0
    best_state = None
    stale = 0

    for epoch in range(1, args.epochs + 1):
        model.train()
        running = 0.0
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
            running += loss.item()
        val_qwk, val_acc = evaluate_model(model, val_loader, device) if val_entries else (0.0, 0.0)
        print(
            f"epoch {epoch}/{args.epochs} loss={running / max(len(train_loader), 1):.4f} "
            f"val_qwk={val_qwk:.4f} val_acc={val_acc:.4f}"
        )
        if val_qwk > best_qwk:
            best_qwk = val_qwk
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            stale = 0
        else:
            stale += 1
        if args.early_stop and stale >= args.early_stop:
            break

    if best_state:
        model.load_state_dict(best_state)

    out_pt = args.output if args.output.is_absolute() else ROOT / args.output
    out_pt.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state": model.state_dict(),
            "state_dict": model.state_dict(),
            "arch": arch_key,
            "preprocess": preprocess,
            "image_size": args.image_size,
            "best_qwk": best_qwk,
            "best_val_qwk": best_qwk,
        },
        out_pt,
    )
    print(f"OK checkpoint {out_pt} best_val_qwk={best_qwk:.4f}")

    if not args.skip_onnx and use_cuda:
        export_onnx(model, out_pt.with_suffix(".onnx"), args.image_size)


if __name__ == "__main__":
    main()
