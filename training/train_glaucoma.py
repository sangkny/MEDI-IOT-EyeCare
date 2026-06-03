#!/usr/bin/env python3
"""Glaucoma 단독 분류 — EfficientNet-B4 + Focal Loss.

- backbone: v4 가중치 초기화 (features/avgpool)
- head: binary (normal=0 / glaucoma=1)
- loss: Focal Loss (gamma, alpha) + WeightedRandomSampler
- 평가: AUC (주), F1, Sensitivity, Specificity
- 목표: val AUC >= 0.90

예:
  python training/train_glaucoma.py \\
    --manifest training/manifests/glaucoma_v1.json \\
    --pretrained models/retinal_v4.pt \\
    --output models/retinal_glaucoma_v1 \\
    --epochs 80 --batch-size 32 --lr 1e-4 --device cuda
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, WeightedRandomSampler

from services.retinal_cnn import _load_efficientnet_backbone, resolve_preprocess_mode
from training.train_multitask import (
    GlaucomaManifestDataset,
    _binary_sample_weights,
    _manifest_splits,
    _resolve_data_dir,
    load_v4_into_multitask,
)

try:
    from torch.amp import GradScaler, autocast
except ImportError:
    from torch.cuda.amp import GradScaler, autocast  # type: ignore[attr-defined]


class GlaucomaClassifier(nn.Module):
    """EfficientNet-B4 + binary glaucoma head."""

    def __init__(self, *, pretrained_imagenet: bool = False) -> None:
        super().__init__()
        backbone = _load_efficientnet_backbone("efficientnet_b4", pretrained=pretrained_imagenet)
        self.features = backbone.features
        self.avgpool = backbone.avgpool
        feat_dim = backbone.classifier[1].in_features
        self.dropout = nn.Dropout(p=0.3)
        self.head = nn.Linear(feat_dim, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = self.avgpool(x)
        x = torch.flatten(x, 1)
        x = self.dropout(x)
        return self.head(x).squeeze(-1)


class FocalLoss(nn.Module):
    """Binary focal loss — positive class alpha (glaucoma) 보정."""

    def __init__(self, *, alpha: float = 0.75, gamma: float = 2.0) -> None:
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        targets = targets.float()
        bce = F.binary_cross_entropy_with_logits(logits, targets, reduction="none")
        pt = torch.exp(-bce)
        alpha_t = self.alpha * targets + (1.0 - self.alpha) * (1.0 - targets)
        return (alpha_t * (1.0 - pt).pow(self.gamma) * bce).mean()


@dataclass
class GlaucomaMetrics:
    auc: float
    f1: float
    sensitivity: float
    specificity: float


@torch.no_grad()
def eval_glaucoma(
    model: GlaucomaClassifier, loader: DataLoader, device: torch.device
) -> GlaucomaMetrics:
    from sklearn.metrics import confusion_matrix, f1_score, roc_auc_score

    if len(loader.dataset) == 0:  # type: ignore[arg-type]
        return GlaucomaMetrics(0.0, 0.0, 0.0, 0.0)

    model.eval()
    ys: list[int] = []
    scores: list[float] = []
    for xb, yb in loader:
        xb = xb.to(device)
        logits = model(xb)
        scores.extend(torch.sigmoid(logits).cpu().tolist())
        ys.extend(yb.tolist())

    if len(set(ys)) < 2:
        return GlaucomaMetrics(0.0, 0.0, 0.0, 0.0)

    preds = [1 if s >= 0.5 else 0 for s in scores]
    auc = float(roc_auc_score(ys, scores))
    f1 = float(f1_score(ys, preds, zero_division=0))
    tn, fp, fn, tp = confusion_matrix(ys, preds, labels=[0, 1]).ravel()
    sensitivity = float(tp / (tp + fn)) if (tp + fn) else 0.0
    specificity = float(tn / (tn + fp)) if (tn + fp) else 0.0
    return GlaucomaMetrics(auc=auc, f1=f1, sensitivity=sensitivity, specificity=specificity)


def load_v4_backbone(model: GlaucomaClassifier, path: Path) -> None:
    """v4 .pt → shared backbone (MultiTask 로더 재사용)."""
    from training.train_multitask import MultiTaskEyeCareModel

    bridge = MultiTaskEyeCareModel(pretrained_imagenet=False)
    load_v4_into_multitask(bridge, path)
    model.features.load_state_dict(bridge.features.state_dict())
    model.avgpool.load_state_dict(bridge.avgpool.state_dict())


def main() -> None:
    p = argparse.ArgumentParser(description="Glaucoma standalone training")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--pretrained", type=Path, default=ROOT / "models" / "retinal_v4.pt")
    p.add_argument("--output", type=Path, default=ROOT / "models" / "retinal_glaucoma_v1")
    p.add_argument("--epochs", type=int, default=80)
    p.add_argument("--batch-size", dest="batch_size", type=int, default=32)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--focal-gamma", dest="focal_gamma", type=float, default=2.0)
    p.add_argument("--focal-alpha", dest="focal_alpha", type=float, default=0.75)
    p.add_argument("--image-size", dest="image_size", type=int, default=224)
    p.add_argument("--device", default="cuda")
    p.add_argument("--early-stop", dest="early_stop", type=int, default=12)
    p.add_argument("--no-amp", action="store_true")
    args = p.parse_args()

    manifest_path = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    train_entries, val_entries, test_entries = _manifest_splits(data)
    data_dir = _resolve_data_dir(data["data_dir"])
    preprocess = resolve_preprocess_mode("clahe")

    use_cuda = args.device == "cuda" and torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")
    use_amp = use_cuda and not args.no_amp

    train_ds = GlaucomaManifestDataset(
        train_entries, data_dir, image_size=args.image_size, preprocess=preprocess, augment=True
    )
    val_ds = GlaucomaManifestDataset(
        val_entries, data_dir, image_size=args.image_size, preprocess=preprocess, augment=False
    )
    test_ds = GlaucomaManifestDataset(
        test_entries, data_dir, image_size=args.image_size, preprocess=preprocess, augment=False
    )

    train_loader = DataLoader(
        train_ds,
        batch_size=args.batch_size,
        sampler=WeightedRandomSampler(
            weights=_binary_sample_weights(train_entries),
            num_samples=len(train_ds),
            replacement=True,
        ),
        num_workers=4,
        pin_memory=use_cuda,
    )
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=2)
    test_loader = DataLoader(test_ds, batch_size=args.batch_size, shuffle=False, num_workers=2)

    pretrained_path = args.pretrained if args.pretrained.is_absolute() else ROOT / args.pretrained
    model = GlaucomaClassifier(pretrained_imagenet=not pretrained_path.is_file())
    if pretrained_path.is_file():
        load_v4_backbone(model, pretrained_path)
    model.to(device)

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(args.epochs, 1))
    scaler = GradScaler("cuda", enabled=use_amp)
    criterion = FocalLoss(alpha=args.focal_alpha, gamma=args.focal_gamma)

    out_dir = args.output if args.output.is_absolute() else ROOT / args.output
    out_dir.mkdir(parents=True, exist_ok=True)
    best_pt = out_dir / "best.pt"

    best_auc = -1.0
    best_state = None
    stale = 0

    pos = sum(int(e.get("glaucoma_grade", e.get("label", 0))) for e in train_entries)
    print(
        f"glaucoma train={len(train_entries)} pos={pos} neg={len(train_entries)-pos} "
        f"focal(alpha={args.focal_alpha}, gamma={args.focal_gamma}) device={device} amp={use_amp}"
    )

    for epoch in range(1, args.epochs + 1):
        model.train()
        running = 0.0
        for xb, yb in train_loader:
            xb = xb.to(device)
            yb = yb.to(device).float()
            opt.zero_grad(set_to_none=True)
            with autocast("cuda", enabled=use_amp):
                logits = model(xb)
                loss = criterion(logits, yb)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            running += loss.item()

        scheduler.step()
        val_m = eval_glaucoma(model, val_loader, device)
        print(
            f"epoch {epoch}/{args.epochs} loss={running/len(train_loader):.4f} "
            f"val_auc={val_m.auc:.4f} f1={val_m.f1:.4f} "
            f"sens={val_m.sensitivity:.4f} spec={val_m.specificity:.4f}"
        )

        if val_m.auc > best_auc:
            best_auc = val_m.auc
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            stale = 0
        else:
            stale += 1
        if args.early_stop and stale >= args.early_stop:
            print(f"early_stop patience={args.early_stop}")
            break

    if best_state:
        model.load_state_dict(best_state)

    val_m = eval_glaucoma(model, val_loader, device)
    test_m = eval_glaucoma(model, test_loader, device)

    torch.save(
        {
            "model_state": model.state_dict(),
            "arch": "efficientnet_b4_glaucoma",
            "best_val_auc": val_m.auc,
            "test_auc": test_m.auc,
        },
        best_pt,
    )

    meta = {
        "arch": "efficientnet_b4_glaucoma",
        "manifest": manifest_path.name,
        "preprocess": preprocess,
        "image_size": args.image_size,
        "focal_alpha": args.focal_alpha,
        "focal_gamma": args.focal_gamma,
        "best_val_auc": round(val_m.auc, 4),
        "best_val_f1": round(val_m.f1, 4),
        "best_val_sensitivity": round(val_m.sensitivity, 4),
        "best_val_specificity": round(val_m.specificity, 4),
        "test_auc": round(test_m.auc, 4),
        "test_f1": round(test_m.f1, 4),
        "epochs": args.epochs,
        "target_auc": 0.90,
    }
    meta_path = out_dir / "best.meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(
        f"OK {best_pt} val_auc={val_m.auc:.4f} test_auc={test_m.auc:.4f} "
        f"(target>={meta['target_auc']})"
    )


if __name__ == "__main__":
    main()
