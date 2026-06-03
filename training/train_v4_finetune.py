#!/usr/bin/env python3
"""v4 기반 fine-tune — EfficientNet-B4(+SE) · CLAHE · MixUp · CosineAnnealingLR.

목표: val QWK >= 0.83 (운영 v4: 0.8204)

예:
  python training/train_v4_finetune.py \\
    --manifest training/manifests/unified_v4.json \\
    --output models/retinal_v4_ft \\
    --epochs 50 --batch-size 16 --lr 1e-4 \\
    --use-clahe --use-se --mixup 0.4 \\
    --resume models/retinal_v4.pt
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
from torch.utils.data import DataLoader, WeightedRandomSampler

from training.train import (
    FundusManifestDataset,
    _class_weights,
    _load_resume_checkpoint,
    _resolve_resume_path,
    _sample_weights,
    evaluate_model,
    export_onnx,
)
from services.retinal_cnn import build_dr_classifier, resolve_preprocess_mode

try:
    from torch.amp import GradScaler, autocast
except ImportError:
    from torch.cuda.amp import GradScaler, autocast  # type: ignore[attr-defined]


def mixup_batch(
    x: torch.Tensor, y: torch.Tensor, alpha: float
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, float]:
    if alpha <= 0:
        lam = 1.0
        return x, y, y, lam
    lam = float(torch.distributions.Beta(alpha, alpha).sample().item())
    perm = torch.randperm(x.size(0), device=x.device)
    mixed_x = lam * x + (1.0 - lam) * x[perm]
    return mixed_x, y, y[perm], lam


def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    opt: torch.optim.Optimizer,
    loss_fn: nn.Module,
    device: torch.device,
    scaler: GradScaler,
    *,
    mixup_alpha: float,
    use_amp: bool,
) -> float:
    model.train()
    running = 0.0
    for xb, yb in loader:
        xb, yb = xb.to(device), yb.to(device)
        opt.zero_grad(set_to_none=True)
        if mixup_alpha > 0:
            xb, ya, yb2, lam = mixup_batch(xb, yb, mixup_alpha)
            with autocast("cuda", enabled=use_amp):
                logits = model(xb)
                loss = lam * loss_fn(logits, ya) + (1.0 - lam) * loss_fn(logits, yb2)
        else:
            with autocast("cuda", enabled=use_amp):
                loss = loss_fn(model(xb), yb)
        scaler.scale(loss).backward()
        scaler.step(opt)
        scaler.update()
        running += loss.item()
    return running / max(len(loader), 1)


def main() -> None:
    p = argparse.ArgumentParser(description="retinal_v4 fine-tune")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--output", type=Path, default=ROOT / "models" / "retinal_v4_ft")
    p.add_argument("--epochs", type=int, default=50)
    p.add_argument("--batch-size", dest="batch_size", type=int, default=16)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--image-size", dest="image_size", type=int, default=224)
    p.add_argument("--early-stop", dest="early_stop", type=int, default=8)
    p.add_argument("--device", default="cuda")
    p.add_argument("--use-clahe", action="store_true", help="CLAHE 전처리 (기본 clahe)")
    p.add_argument("--use-se", action="store_true", help="EfficientNet-B4 + SE Block")
    p.add_argument("--mixup", type=float, default=0.4, help="MixUp alpha (0=off)")
    p.add_argument("--label-smoothing", dest="label_smoothing", type=float, default=0.1)
    p.add_argument("--resume", type=Path, default=None, help="v4 .pt 체크포인트")
    p.add_argument("--resume-epoch", dest="resume_epoch", type=int, default=0)
    p.add_argument("--no-amp", action="store_true")
    p.add_argument("--skip-onnx", action="store_true")
    args = p.parse_args()

    manifest_path = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
    if not manifest_path.is_file():
        raise SystemExit(f"manifest not found: {manifest_path}")

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data_dir = Path(data["data_dir"])
    if not data_dir.is_absolute():
        data_dir = ROOT / data_dir
    train_entries = data.get("train") or []
    val_entries = data.get("val") or data.get("test") or []
    if not train_entries:
        raise SystemExit("manifest train split empty")

    preprocess = resolve_preprocess_mode("clahe" if args.use_clahe else "clahe")
    arch = "efficientnet_b4_se" if args.use_se else "efficientnet_b4"

    use_cuda = args.device == "cuda" and torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")
    use_amp = use_cuda and not args.no_amp

    train_ds = FundusManifestDataset(
        train_entries, data_dir, image_size=args.image_size, preprocess=preprocess, augment=True
    )
    val_ds = FundusManifestDataset(
        val_entries, data_dir, image_size=args.image_size, preprocess=preprocess, augment=False
    )
    train_loader = DataLoader(
        train_ds,
        batch_size=args.batch_size,
        sampler=WeightedRandomSampler(
            weights=_sample_weights(train_entries),
            num_samples=len(train_entries),
            replacement=True,
        ),
        num_workers=4,
        pin_memory=use_cuda,
    )
    val_loader = DataLoader(
        val_ds, batch_size=args.batch_size, shuffle=False, num_workers=4, pin_memory=use_cuda
    )

    model, arch_key = build_dr_classifier(arch=arch, pretrained=not bool(args.resume))
    model.to(device)

    start_epoch = 0
    best_qwk = -1.0
    resume_path = args.resume
    if resume_path is None:
        default_v4 = ROOT / "models" / "retinal_v4.pt"
        if default_v4.is_file():
            resume_path = default_v4
    if resume_path:
        rp = _resolve_resume_path(resume_path)
        ckpt = torch.load(rp, map_location=device, weights_only=False)
        state = (
            ckpt.get("model_state")
            or ckpt.get("state_dict")
            or (ckpt if isinstance(ckpt, dict) else None)
        )
        if isinstance(state, dict) and state:
            missing, unexpected = model.load_state_dict(state, strict=False)
            start_epoch = int(
                ckpt.get("epoch", args.resume_epoch) if isinstance(ckpt, dict) else args.resume_epoch
            )
            best_qwk = float(
                ckpt.get("best_qwk", ckpt.get("best_val_qwk", -1.0))
                if isinstance(ckpt, dict)
                else -1.0
            )
            print(
                f"Resume strict=False from {rp.name}: "
                f"missing={len(missing)} unexpected={len(unexpected)} "
                f"epoch={start_epoch} best_qwk={best_qwk:.4f}"
            )
        else:
            start_epoch, best_qwk = _load_resume_checkpoint(
                model, rp, device, args.resume_epoch
            )

    class_weights = _class_weights(train_entries).to(device)
    loss_fn = nn.CrossEntropyLoss(weight=class_weights, label_smoothing=args.label_smoothing)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(args.epochs, 1))
    scaler = GradScaler("cuda", enabled=use_amp)

    out_dir = args.output if args.output.is_absolute() else ROOT / args.output
    out_dir.mkdir(parents=True, exist_ok=True)
    best_pt = out_dir / "best.pt"

    best_state = None
    stale = 0
    last_epoch = start_epoch

    print(
        f"v4_finetune arch={arch_key} train={len(train_entries)} val={len(val_entries)} "
        f"mixup={args.mixup} device={device} amp={use_amp}"
    )

    for epoch in range(start_epoch + 1, args.epochs + 1):
        last_epoch = epoch
        loss_avg = train_one_epoch(
            model,
            train_loader,
            opt,
            loss_fn,
            device,
            scaler,
            mixup_alpha=args.mixup,
            use_amp=use_amp,
        )
        scheduler.step()
        val_qwk, val_acc = evaluate_model(model, val_loader, device) if val_entries else (0.0, 0.0)
        print(
            f"epoch {epoch}/{args.epochs} loss={loss_avg:.4f} "
            f"val_qwk={val_qwk:.4f} val_acc={val_acc:.4f}"
        )
        if val_qwk > best_qwk:
            best_qwk = val_qwk
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            stale = 0
        else:
            stale += 1
        if args.early_stop and stale >= args.early_stop:
            print(f"early_stop patience={args.early_stop}")
            break

    if best_state:
        model.load_state_dict(best_state)

    torch.save(
        {
            "model_state": model.state_dict(),
            "state_dict": model.state_dict(),
            "epoch": last_epoch,
            "best_qwk": best_qwk,
            "best_val_qwk": best_qwk,
            "arch": arch_key,
            "preprocess": preprocess,
            "image_size": args.image_size,
        },
        best_pt,
    )
    print(f"OK checkpoint {best_pt} best_val_qwk={best_qwk:.4f}")

    if not args.skip_onnx:
        onnx_path = out_dir / "best.onnx"
        export_onnx(model, onnx_path, args.image_size)
        print(f"OK onnx {onnx_path}")

    meta = {
        "arch": arch_key,
        "preprocess": preprocess,
        "image_size": args.image_size,
        "onnx": "best.onnx",
        "pt": "best.pt",
        "version": "v4-finetune-v1",
        "trained_on": manifest_path.name,
        "epochs": args.epochs,
        "best_val_qwk": round(best_qwk, 4),
        "qwk": round(best_qwk, 4),
        "mixup": args.mixup,
        "label_smoothing": args.label_smoothing,
    }
    meta_path = out_dir / "best.meta.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK meta {meta_path}")


if __name__ == "__main__":
    main()
