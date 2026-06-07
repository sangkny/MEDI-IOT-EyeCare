#!/usr/bin/env python3
"""v10 통합 멀티태스크 — DR + Glaucoma + AMD + Myopia + Multidisease (5-head).

- backbone: EfficientNet-B4 (retinal_v4.pt)
- warm-up ep1~10: backbone freeze, heads only
- fine-tune ep11+: full model lr=1e-5 (default head lr=1e-4 warm-up)

예:
  python training/train_v10.py \\
    --manifest training/manifests/unified_v10.json \\
    --pretrained models/retinal_v4.pt \\
    --output models/retinal_v10 \\
    --epochs 60 --batch-size 32 --device cuda
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset

from services.retinal_cnn import (
    DR_NUM_CLASSES,
    _load_efficientnet_backbone,
    preprocess_fundus_array,
    resolve_preprocess_mode,
)
from training.make_manifest import MULTIDISEASE_TRAIN_CLASSES
from training.train_amd import FocalLoss
from training.train_multitask import (
    MultiTaskEyeCareModel,
    _manifest_splits,
    _resolve_data_dir,
    dr_mse_loss,
    load_v4_into_multitask,
    quadratic_weighted_kappa,
)

try:
    from torch.amp import GradScaler, autocast
except ImportError:
    from torch.cuda.amp import GradScaler, autocast  # type: ignore[attr-defined]

LOSS_WEIGHTS = {
    "dr": 0.3,
    "glaucoma": 0.2,
    "amd": 0.2,
    "myopia": 0.2,
    "multidisease": 0.1,
}
WARMUP_EPOCHS = 10
MULTI_NUM_CLASSES = len(MULTIDISEASE_TRAIN_CLASSES)


class MultiTaskV10Model(nn.Module):
    """EfficientNet-B4 + 5-task heads."""

    def __init__(self, *, pretrained_imagenet: bool = False) -> None:
        super().__init__()
        backbone = _load_efficientnet_backbone("efficientnet_b4", pretrained=pretrained_imagenet)
        self.features = backbone.features
        self.avgpool = backbone.avgpool
        self.feat_dim = backbone.classifier[1].in_features
        self.dropout = nn.Dropout(p=0.3)
        self.dr_head = nn.Linear(self.feat_dim, DR_NUM_CLASSES)
        self.gl_head = nn.Linear(self.feat_dim, 1)
        self.amd_head = nn.Linear(self.feat_dim, 1)
        self.myo_head = nn.Linear(self.feat_dim, 1)
        self.multi_head = nn.Linear(self.feat_dim, MULTI_NUM_CLASSES)

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = self.avgpool(x)
        x = torch.flatten(x, 1)
        return self.dropout(x)

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        h = self.encode(x)
        return {
            "dr": self.dr_head(h),
            "glaucoma": self.gl_head(h).squeeze(-1),
            "amd": self.amd_head(h).squeeze(-1),
            "myopia": self.myo_head(h).squeeze(-1),
            "multidisease": self.multi_head(h),
        }

    def set_backbone_trainable(self, trainable: bool) -> None:
        for p in self.features.parameters():
            p.requires_grad = trainable
        for p in self.avgpool.parameters():
            p.requires_grad = trainable


@dataclass
class V10BatchLabels:
    dr: torch.Tensor
    glaucoma: torch.Tensor
    amd: torch.Tensor
    myopia: torch.Tensor
    multidisease: torch.Tensor
    mask_dr: torch.Tensor
    mask_gl: torch.Tensor
    mask_amd: torch.Tensor
    mask_myo: torch.Tensor
    mask_multi: torch.Tensor


class V10Dataset(Dataset):
    """통합 manifest — available_labels, 결측은 NaN."""

    def __init__(
        self,
        entries: list[dict],
        data_dir: Path,
        *,
        class_names: tuple[str, ...] = MULTIDISEASE_TRAIN_CLASSES,
        image_size: int = 224,
        preprocess: str = "clahe",
        augment: bool = False,
    ) -> None:
        self.entries = entries
        self.data_dir = data_dir
        self.class_names = class_names
        self.image_size = image_size
        self.preprocess = preprocess
        self.augment = augment

    def __len__(self) -> int:
        return len(self.entries)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, dict[str, float | dict[str, float] | None]]:
        from PIL import Image
        from torchvision import transforms as T

        entry = self.entries[idx]
        al = entry.get("available_labels") or {}
        img = Image.open(self.data_dir / entry["path"]).convert("RGB")
        arr = preprocess_fundus_array(__import__("numpy").array(img), mode=self.preprocess)
        img = Image.fromarray(arr).resize((self.image_size, self.image_size))
        transform = (
            T.Compose(
                [
                    T.RandomHorizontalFlip(),
                    T.RandomRotation(15),
                    T.ColorJitter(0.15, 0.15, 0.1),
                    T.ToTensor(),
                ]
            )
            if self.augment
            else T.ToTensor()
        )
        labels: dict[str, float | dict[str, float] | None] = {
            "dr": float(al["dr"]) if "dr" in al else math.nan,
            "glaucoma": float(al["glaucoma"]) if "glaucoma" in al else math.nan,
            "amd": float(al["amd"]) if "amd" in al else math.nan,
            "myopia": float(al["myopia"]) if "myopia" in al else math.nan,
            "multidisease": dict(al["multidisease"]) if "multidisease" in al else None,
        }
        return transform(img), labels


def _collate_v10(batch: list) -> tuple[torch.Tensor, V10BatchLabels]:
    imgs = torch.stack([b[0] for b in batch])
    n = len(batch)
    dr = torch.full((n,), float("nan"))
    gl = torch.full((n,), float("nan"))
    amd = torch.full((n,), float("nan"))
    myo = torch.full((n,), float("nan"))
    multi = torch.full((n, MULTI_NUM_CLASSES), float("nan"))

    for i, (_, labels) in enumerate(batch):
        if not math.isnan(float(labels["dr"])):  # type: ignore[arg-type]
            dr[i] = float(labels["dr"])  # type: ignore[arg-type]
        if not math.isnan(float(labels["glaucoma"])):  # type: ignore[arg-type]
            gl[i] = float(labels["glaucoma"])  # type: ignore[arg-type]
        if not math.isnan(float(labels["amd"])):  # type: ignore[arg-type]
            amd[i] = float(labels["amd"])  # type: ignore[arg-type]
        if not math.isnan(float(labels["myopia"])):  # type: ignore[arg-type]
            myo[i] = float(labels["myopia"])  # type: ignore[arg-type]
        md = labels.get("multidisease")
        if isinstance(md, dict):
            for j, name in enumerate(MULTIDISEASE_TRAIN_CLASSES):
                multi[i, j] = float(md.get(name, 0))

    return imgs, V10BatchLabels(
        dr=dr,
        glaucoma=gl,
        amd=amd,
        myopia=myo,
        multidisease=multi,
        mask_dr=~torch.isnan(dr),
        mask_gl=~torch.isnan(gl),
        mask_amd=~torch.isnan(amd),
        mask_myo=~torch.isnan(myo),
        mask_multi=~torch.isnan(multi).all(dim=1),
    )


class V10Loss(nn.Module):
    """마스킹 기반 5-head weighted loss."""

    def __init__(
        self,
        *,
        multi_pos_weight: torch.Tensor | None = None,
        focal_gamma: float = 2.0,
    ) -> None:
        super().__init__()
        self.focal = FocalLoss(gamma=focal_gamma)
        self.multi_criterion = nn.BCEWithLogitsLoss(
            pos_weight=multi_pos_weight,
            reduction="none",
        )

    def forward(
        self,
        outputs: dict[str, torch.Tensor],
        labels: V10BatchLabels,
    ) -> tuple[torch.Tensor, dict[str, float]]:
        parts: dict[str, torch.Tensor] = {}

        if labels.mask_dr.any():
            parts["dr"] = dr_mse_loss(
                outputs["dr"][labels.mask_dr],
                labels.dr[labels.mask_dr],
            )
        if labels.mask_gl.any():
            parts["glaucoma"] = self.focal(
                outputs["glaucoma"][labels.mask_gl],
                labels.glaucoma[labels.mask_gl],
            )
        if labels.mask_amd.any():
            parts["amd"] = self.focal(
                outputs["amd"][labels.mask_amd],
                labels.amd[labels.mask_amd],
            )
        if labels.mask_myo.any():
            parts["myopia"] = self.focal(
                outputs["myopia"][labels.mask_myo],
                labels.myopia[labels.mask_myo],
            )
        if labels.mask_multi.any():
            logits = outputs["multidisease"][labels.mask_multi]
            targets = labels.multidisease[labels.mask_multi]
            bce = self.multi_criterion(logits, targets).mean(dim=1)
            parts["multidisease"] = bce.mean()

        if not parts:
            zero = outputs["dr"].sum() * 0.0
            return zero, {}

        total = sum(LOSS_WEIGHTS[k] * v for k, v in parts.items())
        return total, {k: float(v.detach()) for k, v in parts.items()}


def load_v4_into_v10(model: MultiTaskV10Model, path: Path) -> None:
    bridge = MultiTaskEyeCareModel(pretrained_imagenet=False)
    load_v4_into_multitask(bridge, path)
    model.features.load_state_dict(bridge.features.state_dict())
    model.avgpool.load_state_dict(bridge.avgpool.state_dict())
    model.dr_head.load_state_dict(bridge.dr_head.state_dict())


@torch.no_grad()
def eval_dr_qwk(model: MultiTaskV10Model, loader: DataLoader, device: torch.device) -> float:
    ys, ps = [], []
    for xb, lb in loader:
        mask = lb.mask_dr
        if not mask.any():
            continue
        xb = xb[mask].to(device)
        logits = model.forward(xb)["dr"]
        ps.extend(logits.argmax(dim=1).cpu().tolist())
        ys.extend(lb.dr[mask].tolist())
    return quadratic_weighted_kappa(ys, ps) if ys else 0.0


@torch.no_grad()
def eval_binary_auc(
    model: MultiTaskV10Model,
    loader: DataLoader,
    device: torch.device,
    task: str,
) -> float:
    from sklearn.metrics import roc_auc_score

    ys, scores = [], []
    for xb, lb in loader:
        if task == "glaucoma":
            mask = lb.mask_gl
        elif task == "amd":
            mask = lb.mask_amd
        else:
            mask = lb.mask_myo
        if not mask.any():
            continue
        xb = xb[mask].to(device)
        logits = model.forward(xb)[task]
        scores.extend(torch.sigmoid(logits).cpu().tolist())
        ys.extend(getattr(lb, task if task != "myopia" else "myopia")[mask].tolist())
    if len(set(int(y) for y in ys)) < 2:
        return 0.0
    return float(roc_auc_score(ys, scores))


@torch.no_grad()
def eval_multidisease_mauc(
    model: MultiTaskV10Model,
    loader: DataLoader,
    device: torch.device,
) -> float:
    from training.train_multidisease import eval_multidisease

    class _Wrap(nn.Module):
        def __init__(self, m: MultiTaskV10Model) -> None:
            super().__init__()
            self.m = m

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return self.m.forward(x)["multidisease"]

    wrap = _Wrap(model)
    filtered = [
        s
        for s in loader.dataset.entries  # type: ignore[attr-defined]
        if (s.get("available_labels") or {}).get("multidisease")
    ]
    if not filtered:
        return 0.0
    ds = V10Dataset(
        filtered,
        loader.dataset.data_dir,  # type: ignore[attr-defined]
        image_size=loader.dataset.image_size,  # type: ignore[attr-defined]
        preprocess=loader.dataset.preprocess,  # type: ignore[attr-defined]
        augment=False,
    )
    sub = DataLoader(ds, batch_size=loader.batch_size, shuffle=False, collate_fn=_collate_v10)
    result = eval_multidisease(wrap, sub, device, MULTIDISEASE_TRAIN_CLASSES)
    return result.mauc


def main() -> None:
    p = argparse.ArgumentParser(description="v10 unified multitask training")
    p.add_argument("--manifest", type=Path, default=ROOT / "training/manifests/unified_v10.json")
    p.add_argument("--pretrained", type=Path, default=ROOT / "models/retinal_v4.pt")
    p.add_argument("--output", type=Path, default=ROOT / "models/retinal_v10")
    p.add_argument("--epochs", type=int, default=60)
    p.add_argument("--batch-size", dest="batch_size", type=int, default=32)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--finetune-lr", dest="finetune_lr", type=float, default=1e-5)
    p.add_argument("--warmup-epochs", dest="warmup_epochs", type=int, default=WARMUP_EPOCHS)
    p.add_argument("--image-size", dest="image_size", type=int, default=224)
    p.add_argument("--device", default="cuda")
    p.add_argument("--early-stop", dest="early_stop", type=int, default=12)
    p.add_argument("--no-amp", action="store_true")
    args = p.parse_args()

    manifest_path = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    train_entries, val_entries, _ = _manifest_splits(data)
    data_dir = _resolve_data_dir(data["data_dir"])
    preprocess = resolve_preprocess_mode("clahe")

    use_cuda = args.device == "cuda" and torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")
    use_amp = use_cuda and not args.no_amp

    train_ds = V10Dataset(
        train_entries, data_dir, image_size=args.image_size, preprocess=preprocess, augment=True
    )
    val_ds = V10Dataset(
        val_entries, data_dir, image_size=args.image_size, preprocess=preprocess, augment=False
    )
    train_loader = DataLoader(
        train_ds,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=4,
        pin_memory=use_cuda,
        collate_fn=_collate_v10,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=2,
        collate_fn=_collate_v10,
    )

    pretrained = args.pretrained if args.pretrained.is_absolute() else ROOT / args.pretrained
    model = MultiTaskV10Model(pretrained_imagenet=not pretrained.is_file())
    if pretrained.is_file():
        load_v4_into_v10(model, pretrained)
    model.to(device)

    criterion = V10Loss()
    opt = torch.optim.AdamW(filter(lambda t: t.requires_grad, model.parameters()), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(args.epochs, 1))
    scaler = GradScaler("cuda", enabled=use_amp)

    out_dir = args.output if args.output.is_absolute() else ROOT / args.output
    out_dir.mkdir(parents=True, exist_ok=True)
    best_pt = out_dir / "best.pt"

    best_score = -1.0
    best_state = None
    stale = 0

    print(
        f"v10 train={len(train_entries)} val={len(val_entries)} "
        f"device={device} amp={use_amp} warmup={args.warmup_epochs}"
    )

    for epoch in range(1, args.epochs + 1):
        if epoch == args.warmup_epochs + 1:
            model.set_backbone_trainable(True)
            for g in opt.param_groups:
                g["lr"] = args.finetune_lr
            print(f"epoch {epoch}: backbone unfrozen, lr={args.finetune_lr}")
        elif epoch <= args.warmup_epochs:
            model.set_backbone_trainable(False)

        model.train()
        running = 0.0
        for xb, lb in train_loader:
            xb = xb.to(device)
            opt.zero_grad(set_to_none=True)
            with autocast("cuda", enabled=use_amp):
                outputs = model.forward(xb)
                loss, _parts = criterion(outputs, lb)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            running += float(loss.detach())

        scheduler.step()

        model.eval()
        qwk = eval_dr_qwk(model, val_loader, device)
        gl_auc = eval_binary_auc(model, val_loader, device, "glaucoma")
        amd_auc = eval_binary_auc(model, val_loader, device, "amd")
        myo_auc = eval_binary_auc(model, val_loader, device, "myopia")
        mauc = eval_multidisease_mauc(model, val_loader, device)
        composite = qwk * 0.3 + gl_auc * 0.2 + amd_auc * 0.2 + myo_auc * 0.2 + mauc * 0.1

        print(
            f"epoch {epoch}/{args.epochs} loss={running/max(len(train_loader),1):.4f} "
            f"QWK={qwk:.4f} GL={gl_auc:.4f} AMD={amd_auc:.4f} MYO={myo_auc:.4f} "
            f"mAUC={mauc:.4f} composite={composite:.4f}"
        )

        if composite > best_score:
            best_score = composite
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
            "arch": "efficientnet_b4_v10",
            "best_composite": best_score,
            "loss_weights": LOSS_WEIGHTS,
        },
        best_pt,
    )
    meta = {
        "arch": "efficientnet_b4_v10",
        "manifest": manifest_path.name,
        "preprocess": preprocess,
        "image_size": args.image_size,
        "best_composite": round(best_score, 4),
        "loss_weights": LOSS_WEIGHTS,
        "warmup_epochs": args.warmup_epochs,
    }
    (out_dir / "best.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"OK {best_pt} composite={best_score:.4f}")


if __name__ == "__main__":
    main()
