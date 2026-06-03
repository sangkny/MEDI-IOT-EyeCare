#!/usr/bin/env python3
"""v9 멀티태스크: DR(5-class) + Glaucoma(binary) — 공유 EfficientNet-B4.

- DR loss: ordinal MSE (softmax 기대등급 vs 라벨) · 평가 QWK
- Glaucoma loss: BCEWithLogits · 평가 AUC
- total: 0.6 * dr_loss + 0.4 * glaucoma_loss (배치별 해당 태스크만)

예:
  python training/train_multitask.py \\
    --dr-manifest training/manifests/unified_v4.json \\
    --glaucoma-manifest training/manifests/glaucoma_v1.json \\
    --pretrained models/retinal_v4.pt \\
    --output models/retinal_v9_multitask \\
    --epochs 60 --batch-size 16 --lr 1e-4 --device cuda
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from itertools import cycle
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler

from services.retinal_cnn import (
    DR_NUM_CLASSES,
    _load_efficientnet_backbone,
    preprocess_fundus_array,
    resolve_preprocess_mode,
)
from training.train import (
    _sample_weights,
    quadratic_weighted_kappa,
)

try:
    from torch.amp import GradScaler, autocast
except ImportError:
    from torch.cuda.amp import GradScaler, autocast  # type: ignore[attr-defined]

DR_LOSS_WEIGHT = 0.6
GLAUCOMA_LOSS_WEIGHT = 0.4


class MultiTaskEyeCareModel(nn.Module):
    """EfficientNet-B4 백본 + DR / Glaucoma 헤드."""

    def __init__(self, *, pretrained_imagenet: bool = False) -> None:
        super().__init__()
        backbone = _load_efficientnet_backbone("efficientnet_b4", pretrained=pretrained_imagenet)
        self.features = backbone.features
        self.avgpool = backbone.avgpool
        self.feat_dim = backbone.classifier[1].in_features
        self.dropout = nn.Dropout(p=0.3)
        self.dr_head = nn.Linear(self.feat_dim, DR_NUM_CLASSES)
        self.glaucoma_head = nn.Linear(self.feat_dim, 1)

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = self.avgpool(x)
        x = torch.flatten(x, 1)
        return self.dropout(x)

    def forward_dr(self, x: torch.Tensor) -> torch.Tensor:
        return self.dr_head(self.encode(x))

    def forward_glaucoma(self, x: torch.Tensor) -> torch.Tensor:
        return self.glaucoma_head(self.encode(x)).squeeze(-1)


def _manifest_splits(data: dict) -> tuple[list[dict], list[dict], list[dict]]:
    if data.get("train"):
        return (
            list(data["train"]),
            list(data.get("val") or []),
            list(data.get("test") or []),
        )
    samples = list(data.get("samples") or [])
    train = [s for s in samples if s.get("split") == "train"]
    val = [s for s in samples if s.get("split") == "val"]
    test = [s for s in samples if s.get("split") == "test"]
    return train, val, test


class DRManifestDataset(Dataset):
    def __init__(
        self,
        entries: list[dict],
        data_dir: Path,
        *,
        image_size: int = 224,
        preprocess: str = "clahe",
        augment: bool = False,
    ) -> None:
        self.entries = entries
        self.data_dir = data_dir
        self.image_size = image_size
        self.preprocess = preprocess
        self.augment = augment

    def __len__(self) -> int:
        return len(self.entries)

    def __getitem__(self, idx: int):
        from PIL import Image
        from torchvision import transforms as T

        e = self.entries[idx]
        img = Image.open(self.data_dir / e["path"]).convert("RGB")
        arr = preprocess_fundus_array(
            __import__("numpy").array(img), mode=self.preprocess
        )
        img = Image.fromarray(arr).resize((self.image_size, self.image_size))
        t = (
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
        return t(img), int(e["dr_grade"])


class GlaucomaManifestDataset(Dataset):
    def __init__(
        self,
        entries: list[dict],
        data_dir: Path,
        *,
        image_size: int = 224,
        preprocess: str = "clahe",
        augment: bool = False,
    ) -> None:
        self.entries = entries
        self.data_dir = data_dir
        self.image_size = image_size
        self.preprocess = preprocess
        self.augment = augment

    def __len__(self) -> int:
        return len(self.entries)

    def __getitem__(self, idx: int):
        from PIL import Image
        from torchvision import transforms as T

        e = self.entries[idx]
        label = int(e.get("glaucoma_grade", e.get("label", 0)))
        img = Image.open(self.data_dir / e["path"]).convert("RGB")
        arr = preprocess_fundus_array(
            __import__("numpy").array(img), mode=self.preprocess
        )
        img = Image.fromarray(arr).resize((self.image_size, self.image_size))
        t = (
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
        return t(img), label


def _binary_sample_weights(entries: list[dict]) -> list[float]:
    labels = [int(e.get("glaucoma_grade", e.get("label", 0))) for e in entries]
    counts = Counter(labels)
    total = len(labels)
    return [total / (2 * counts[l]) for l in labels]


def dr_mse_loss(logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
    """Ordinal MSE: softmax 기대 DR 등급 vs 정수 라벨."""
    probs = F.softmax(logits, dim=1)
    grades = torch.arange(DR_NUM_CLASSES, device=logits.device, dtype=probs.dtype)
    expected = (probs * grades).sum(dim=1)
    return F.mse_loss(expected, targets.float())


def load_v4_into_multitask(model: MultiTaskEyeCareModel, path: Path) -> None:
    """retinal_v4.pt → backbone + dr_head (strict=False)."""
    if path.suffix.lower() == ".onnx":
        pt_path = path.with_suffix(".pt")
        if pt_path.is_file():
            path = pt_path
        else:
            print(f"WARN: ONNX only at {path} — use .pt for init; ImageNet backbone only")
            return
    if not path.is_file():
        print(f"WARN: pretrained not found: {path}")
        return

    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    state = ckpt.get("model_state") or ckpt.get("state_dict") or ckpt
    if not isinstance(state, dict):
        return

    own = model.state_dict()
    mapped = {}
    for k, v in state.items():
        if k in own and own[k].shape == v.shape:
            mapped[k] = v
        elif k.startswith("classifier.") and k.replace("classifier.", "dr_head.") in own:
            nk = k.replace("classifier.", "dr_head.")
            if own[nk].shape == v.shape:
                mapped[nk] = v
        elif k.startswith("features.") or k.startswith("avgpool."):
            if k in own and own[k].shape == v.shape:
                mapped[k] = v
    missing, unexpected = model.load_state_dict(mapped, strict=False)
    print(
        f"Pretrained {path.name}: loaded={len(mapped)} "
        f"missing={len(missing)} unexpected={len(unexpected)}"
    )


@torch.no_grad()
def eval_dr(model: MultiTaskEyeCareModel, loader: DataLoader, device: torch.device) -> float:
    if len(loader.dataset) == 0:  # type: ignore[arg-type]
        return 0.0
    model.eval()
    ys, ps = [], []
    for xb, yb in loader:
        xb = xb.to(device)
        logits = model.forward_dr(xb)
        ps.extend(logits.argmax(dim=1).cpu().tolist())
        ys.extend(yb.tolist())
    return quadratic_weighted_kappa(ys, ps) if ys else 0.0


@torch.no_grad()
def eval_glaucoma_auc(
    model: MultiTaskEyeCareModel, loader: DataLoader, device: torch.device
) -> float:
    from sklearn.metrics import roc_auc_score

    if len(loader.dataset) == 0:  # type: ignore[arg-type]
        return 0.0
    model.eval()
    ys, scores = [], []
    for xb, yb in loader:
        xb = xb.to(device)
        logits = model.forward_glaucoma(xb)
        scores.extend(torch.sigmoid(logits).cpu().tolist())
        ys.extend(yb.tolist())
    if len(set(ys)) < 2:
        return 0.0
    return float(roc_auc_score(ys, scores))


def _resolve_data_dir(raw: str) -> Path:
    p = Path(raw)
    if p.is_absolute():
        return p
    return ROOT / p


def main() -> None:
    p = argparse.ArgumentParser(description="v9 multitask DR + Glaucoma")
    p.add_argument("--dr-manifest", type=Path, required=True)
    p.add_argument("--glaucoma-manifest", type=Path, required=True)
    p.add_argument("--pretrained", type=Path, default=ROOT / "models" / "retinal_v4.pt")
    p.add_argument("--output", type=Path, default=ROOT / "models" / "retinal_v9_multitask")
    p.add_argument("--epochs", type=int, default=60)
    p.add_argument("--batch-size", dest="batch_size", type=int, default=16)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--image-size", dest="image_size", type=int, default=224)
    p.add_argument("--device", default="cuda")
    p.add_argument("--early-stop", dest="early_stop", type=int, default=10)
    p.add_argument("--no-amp", action="store_true")
    p.add_argument("--skip-onnx", action="store_true")
    args = p.parse_args()

    dr_path = args.dr_manifest if args.dr_manifest.is_absolute() else ROOT / args.dr_manifest
    gl_path = (
        args.glaucoma_manifest
        if args.glaucoma_manifest.is_absolute()
        else ROOT / args.glaucoma_manifest
    )
    dr_data = json.loads(dr_path.read_text(encoding="utf-8"))
    gl_data = json.loads(gl_path.read_text(encoding="utf-8"))

    dr_train, dr_val, _ = _manifest_splits(dr_data)
    gl_train, gl_val, _ = _manifest_splits(gl_data)
    dr_dir = _resolve_data_dir(dr_data["data_dir"])
    gl_dir = _resolve_data_dir(gl_data["data_dir"])

    use_cuda = args.device == "cuda" and torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")
    use_amp = use_cuda and not args.no_amp
    preprocess = resolve_preprocess_mode("clahe")

    dr_train_ds = DRManifestDataset(
        dr_train, dr_dir, image_size=args.image_size, preprocess=preprocess, augment=True
    )
    gl_train_ds = GlaucomaManifestDataset(
        gl_train, gl_dir, image_size=args.image_size, preprocess=preprocess, augment=True
    )
    dr_val_ds = DRManifestDataset(
        dr_val, dr_dir, image_size=args.image_size, preprocess=preprocess, augment=False
    )
    gl_val_ds = GlaucomaManifestDataset(
        gl_val, gl_dir, image_size=args.image_size, preprocess=preprocess, augment=False
    )

    dr_loader = DataLoader(
        dr_train_ds,
        batch_size=args.batch_size,
        sampler=WeightedRandomSampler(
            weights=_sample_weights(dr_train),
            num_samples=len(dr_train_ds),
            replacement=True,
        ),
        num_workers=4,
        pin_memory=use_cuda,
    )
    gl_loader = DataLoader(
        gl_train_ds,
        batch_size=args.batch_size,
        sampler=WeightedRandomSampler(
            weights=_binary_sample_weights(gl_train),
            num_samples=len(gl_train_ds),
            replacement=True,
        ),
        num_workers=4,
        pin_memory=use_cuda,
    )
    dr_val_loader = DataLoader(dr_val_ds, batch_size=args.batch_size, shuffle=False, num_workers=2)
    gl_val_loader = DataLoader(gl_val_ds, batch_size=args.batch_size, shuffle=False, num_workers=2)

    model = MultiTaskEyeCareModel(pretrained_imagenet=not args.pretrained.is_file())
    load_v4_into_multitask(model, args.pretrained if args.pretrained.is_absolute() else ROOT / args.pretrained)
    model.to(device)

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(args.epochs, 1))
    scaler = GradScaler("cuda", enabled=use_amp)
    bce = nn.BCEWithLogitsLoss()

    out_dir = args.output if args.output.is_absolute() else ROOT / args.output
    out_dir.mkdir(parents=True, exist_ok=True)
    best_pt = out_dir / "best.pt"

    best_score = -1.0
    best_state = None
    stale = 0

    print(
        f"v9 multitask dr_train={len(dr_train)} gl_train={len(gl_train)} "
        f"device={device} amp={use_amp}"
    )

    for epoch in range(1, args.epochs + 1):
        model.train()
        dr_iter = cycle(dr_loader)
        gl_iter = cycle(gl_loader)
        steps = max(len(dr_loader), len(gl_loader))
        running_dr = running_gl = 0.0

        for step in range(steps):
            xb, yb = next(dr_iter)
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad(set_to_none=True)
            with autocast("cuda", enabled=use_amp):
                dr_logits = model.forward_dr(xb)
                loss_dr = dr_mse_loss(dr_logits, yb) * DR_LOSS_WEIGHT
            scaler.scale(loss_dr).backward()
            scaler.step(opt)
            scaler.update()
            running_dr += loss_dr.item()

            xg, yg = next(gl_iter)
            xg, yg = xg.to(device), yg.to(device).float()
            opt.zero_grad(set_to_none=True)
            with autocast("cuda", enabled=use_amp):
                gl_logits = model.forward_glaucoma(xg)
                loss_gl = bce(gl_logits, yg) * GLAUCOMA_LOSS_WEIGHT
            scaler.scale(loss_gl).backward()
            scaler.step(opt)
            scaler.update()
            running_gl += loss_gl.item()

        scheduler.step()
        val_qwk = eval_dr(model, dr_val_loader, device)
        val_auc = eval_glaucoma_auc(model, gl_val_loader, device)
        combined = val_qwk + val_auc
        print(
            f"epoch {epoch}/{args.epochs} dr_loss={running_dr/steps:.4f} "
            f"gl_loss={running_gl/steps:.4f} val_qwk={val_qwk:.4f} val_auc={val_auc:.4f}"
        )

        if combined > best_score:
            best_score = combined
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            stale = 0
        else:
            stale += 1
        if args.early_stop and stale >= args.early_stop:
            print(f"early_stop patience={args.early_stop}")
            break

    if best_state:
        model.load_state_dict(best_state)

    val_qwk = eval_dr(model, dr_val_loader, device)
    val_auc = eval_glaucoma_auc(model, gl_val_loader, device)

    torch.save(
        {
            "model_state": model.state_dict(),
            "epoch": epoch,
            "best_val_qwk": val_qwk,
            "best_val_auc": val_auc,
            "arch": "efficientnet_b4_multitask",
        },
        best_pt,
    )
    print(f"OK checkpoint {best_pt} val_qwk={val_qwk:.4f} val_auc={val_auc:.4f}")

    meta = {
        "arch": "efficientnet_b4_multitask",
        "dr_manifest": dr_path.name,
        "glaucoma_manifest": gl_path.name,
        "best_val_qwk": round(val_qwk, 4),
        "best_val_auc": round(val_auc, 4),
        "epochs": args.epochs,
        "dr_loss_weight": DR_LOSS_WEIGHT,
        "glaucoma_loss_weight": GLAUCOMA_LOSS_WEIGHT,
    }
    meta_path = out_dir / "best.meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print("OK train_multitask done")


if __name__ == "__main__":
    main()
