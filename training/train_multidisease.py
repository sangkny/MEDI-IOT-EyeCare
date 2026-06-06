#!/usr/bin/env python3
"""다질환 멀티레이블 분류 — EfficientNet-B4 + 28-class sigmoid head.

- backbone: retinal_v4.pt (features/avgpool)
- head: 28-class BCE (주요 질환, 희귀 18종 제외)
- loss: BCEWithLogits + pos_weight (클래스 불균형)
- 평가: per-class AUC + mAUC (목표 >= 0.85)

예:
  python training/train_multidisease.py \\
    --manifest training/manifests/multidisease_v1.json \\
    --pretrained models/retinal_v4.pt \\
    --output models/retinal_multidisease_v1 \\
    --epochs 60 --batch-size 32 --lr 1e-4 --device cuda
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset

from services.retinal_cnn import _load_efficientnet_backbone, preprocess_fundus_array, resolve_preprocess_mode
from training.make_manifest import MULTIDISEASE_TRAIN_CLASSES
from training.train_multitask import _manifest_splits, _resolve_data_dir, load_v4_into_multitask

try:
    from torch.amp import GradScaler, autocast
except ImportError:
    from torch.cuda.amp import GradScaler, autocast  # type: ignore[attr-defined]

NUM_CLASSES = len(MULTIDISEASE_TRAIN_CLASSES)


class MultidiseaseClassifier(nn.Module):
    """EfficientNet-B4 + multi-label head."""

    def __init__(self, *, num_classes: int = NUM_CLASSES, pretrained_imagenet: bool = False) -> None:
        super().__init__()
        backbone = _load_efficientnet_backbone("efficientnet_b4", pretrained=pretrained_imagenet)
        self.features = backbone.features
        self.avgpool = backbone.avgpool
        feat_dim = backbone.classifier[1].in_features
        self.dropout = nn.Dropout(p=0.3)
        self.head = nn.Linear(feat_dim, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = self.avgpool(x)
        x = torch.flatten(x, 1)
        x = self.dropout(x)
        return self.head(x)


class MultidiseaseManifestDataset(Dataset):
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

    def __getitem__(self, idx: int):
        from PIL import Image
        from torchvision import transforms as T

        entry = self.entries[idx]
        labels = entry.get("labels") or {}
        target = torch.tensor(
            [float(int(labels.get(name, 0))) for name in self.class_names],
            dtype=torch.float32,
        )
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
        return transform(img), target


def load_v4_backbone(model: MultidiseaseClassifier, path: Path) -> None:
    from training.train_multitask import MultiTaskEyeCareModel

    bridge = MultiTaskEyeCareModel(pretrained_imagenet=False)
    load_v4_into_multitask(bridge, path)
    model.features.load_state_dict(bridge.features.state_dict())
    model.avgpool.load_state_dict(bridge.avgpool.state_dict())


def compute_pos_weight(entries: list[dict], class_names: tuple[str, ...]) -> torch.Tensor:
    n = max(len(entries), 1)
    weights: list[float] = []
    for name in class_names:
        pos = sum(int((e.get("labels") or {}).get(name, 0)) for e in entries)
        neg = n - pos
        weights.append(neg / max(pos, 1))
    return torch.tensor(weights, dtype=torch.float32)


@dataclass
class MultidiseaseMetrics:
    mauc: float
    per_class_auc: dict[str, float]


@torch.no_grad()
def eval_multidisease(
    model: MultidiseaseClassifier,
    loader: DataLoader,
    device: torch.device,
    class_names: tuple[str, ...],
) -> MultidiseaseMetrics:
    from sklearn.metrics import roc_auc_score

    if len(loader.dataset) == 0:  # type: ignore[arg-type]
        return MultidiseaseMetrics(0.0, {})

    model.eval()
    all_targets: list[list[float]] = []
    all_scores: list[list[float]] = []
    for xb, yb in loader:
        xb = xb.to(device)
        logits = model(xb)
        all_scores.extend(torch.sigmoid(logits).cpu().tolist())
        all_targets.extend(yb.tolist())

    per_class: dict[str, float] = {}
    auc_values: list[float] = []
    for idx, name in enumerate(class_names):
        ys = [row[idx] for row in all_targets]
        scores = [row[idx] for row in all_scores]
        if len(set(ys)) < 2:
            continue
        auc = float(roc_auc_score(ys, scores))
        per_class[name] = auc
        auc_values.append(auc)

    mauc = float(sum(auc_values) / len(auc_values)) if auc_values else 0.0
    return MultidiseaseMetrics(mauc=mauc, per_class_auc=per_class)


def main() -> None:
    p = argparse.ArgumentParser(description="Multidisease multi-label training")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--pretrained", type=Path, default=ROOT / "models" / "retinal_v4.pt")
    p.add_argument("--output", type=Path, default=ROOT / "models" / "retinal_multidisease_v1")
    p.add_argument("--epochs", type=int, default=60)
    p.add_argument("--batch-size", dest="batch_size", type=int, default=32)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--image-size", dest="image_size", type=int, default=224)
    p.add_argument("--device", default="cuda")
    p.add_argument("--early-stop", dest="early_stop", type=int, default=12)
    p.add_argument("--no-amp", action="store_true")
    args = p.parse_args()

    manifest_path = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    class_names = tuple(data.get("label_classes") or MULTIDISEASE_TRAIN_CLASSES)
    train_entries, val_entries, test_entries = _manifest_splits(data)
    data_dir = _resolve_data_dir(data["data_dir"])
    preprocess = resolve_preprocess_mode("clahe")

    use_cuda = args.device == "cuda" and torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")
    use_amp = use_cuda and not args.no_amp

    train_ds = MultidiseaseManifestDataset(
        train_entries,
        data_dir,
        class_names=class_names,
        image_size=args.image_size,
        preprocess=preprocess,
        augment=True,
    )
    val_ds = MultidiseaseManifestDataset(
        val_entries,
        data_dir,
        class_names=class_names,
        image_size=args.image_size,
        preprocess=preprocess,
        augment=False,
    )
    test_ds = MultidiseaseManifestDataset(
        test_entries,
        data_dir,
        class_names=class_names,
        image_size=args.image_size,
        preprocess=preprocess,
        augment=False,
    )

    train_loader = DataLoader(
        train_ds,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=4,
        pin_memory=use_cuda,
    )
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=2)
    test_loader = DataLoader(test_ds, batch_size=args.batch_size, shuffle=False, num_workers=2)

    pretrained_path = args.pretrained if args.pretrained.is_absolute() else ROOT / args.pretrained
    model = MultidiseaseClassifier(num_classes=len(class_names), pretrained_imagenet=not pretrained_path.is_file())
    if pretrained_path.is_file():
        load_v4_backbone(model, pretrained_path)
    model.to(device)

    pos_weight = compute_pos_weight(train_entries, class_names).to(device)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(args.epochs, 1))
    scaler = GradScaler("cuda", enabled=use_amp)

    out_dir = args.output if args.output.is_absolute() else ROOT / args.output
    out_dir.mkdir(parents=True, exist_ok=True)
    best_pt = out_dir / "best.pt"

    best_mauc = -1.0
    best_state = None
    stale = 0

    print(
        f"multidisease train={len(train_entries)} classes={len(class_names)} "
        f"pos_weight[dr]={pos_weight[0]:.2f} device={device} amp={use_amp}"
    )

    for epoch in range(1, args.epochs + 1):
        model.train()
        running = 0.0
        for xb, yb in train_loader:
            xb = xb.to(device)
            yb = yb.to(device)
            opt.zero_grad(set_to_none=True)
            with autocast("cuda", enabled=use_amp):
                logits = model(xb)
                loss = criterion(logits, yb)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            running += loss.item()

        scheduler.step()
        val_m = eval_multidisease(model, val_loader, device, class_names)
        top5 = sorted(val_m.per_class_auc.items(), key=lambda kv: kv[1], reverse=True)[:5]
        top5_str = ", ".join(f"{k}={v:.3f}" for k, v in top5)
        print(
            f"epoch {epoch}/{args.epochs} loss={running/max(len(train_loader),1):.4f} "
            f"val_mauc={val_m.mauc:.4f} top5=[{top5_str}]"
        )

        if val_m.mauc > best_mauc:
            best_mauc = val_m.mauc
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            stale = 0
        else:
            stale += 1
        if args.early_stop and stale >= args.early_stop:
            print(f"early_stop patience={args.early_stop}")
            break

    if best_state:
        model.load_state_dict(best_state)

    val_m = eval_multidisease(model, val_loader, device, class_names)
    test_m = eval_multidisease(model, test_loader, device, class_names)

    torch.save(
        {
            "model_state": model.state_dict(),
            "arch": "efficientnet_b4_multidisease",
            "label_classes": list(class_names),
            "best_val_mauc": val_m.mauc,
            "test_mauc": test_m.mauc,
        },
        best_pt,
    )

    meta = {
        "arch": "efficientnet_b4_multidisease",
        "manifest": manifest_path.name,
        "preprocess": preprocess,
        "image_size": args.image_size,
        "label_classes": list(class_names),
        "best_val_mauc": round(val_m.mauc, 4),
        "best_val_per_class_auc": {k: round(v, 4) for k, v in val_m.per_class_auc.items()},
        "test_mauc": round(test_m.mauc, 4),
        "test_per_class_auc": {k: round(v, 4) for k, v in test_m.per_class_auc.items()},
        "epochs": args.epochs,
        "target_mauc": 0.85,
    }
    meta_path = out_dir / "best.meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(
        f"OK {best_pt} val_mauc={val_m.mauc:.4f} test_mauc={test_m.mauc:.4f} "
        f"(target>={meta['target_mauc']})"
    )


if __name__ == "__main__":
    main()
