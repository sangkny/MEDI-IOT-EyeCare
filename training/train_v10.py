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

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler

from services.cdr_estimator import cdr_from_seg_logits
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
SEG_LOSS_WEIGHT = 0.05
SEG_COMPOSITE_WEIGHT = 0.05
SEG_IGNORE_INDEX = -1
WARMUP_EPOCHS = 10
MULTI_NUM_CLASSES = len(MULTIDISEASE_TRAIN_CLASSES)


class MultiTaskV10Model(nn.Module):
    """EfficientNet-B4 + 5-task heads (+ optional disc/cup seg head)."""

    def __init__(
        self,
        *,
        pretrained_imagenet: bool = False,
        seg_head: bool = False,
        image_size: int = 224,
    ) -> None:
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
        self.seg_head_enabled = seg_head
        self.image_size = image_size
        if seg_head:
            self.seg_head = nn.Sequential(
                nn.Conv2d(self.feat_dim, 256, kernel_size=1),
                nn.ReLU(inplace=True),
                nn.Upsample(
                    size=(image_size, image_size),
                    mode="bilinear",
                    align_corners=False,
                ),
                nn.Conv2d(256, 3, kernel_size=1),
            )

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        feat_map = self.features(x)
        x = self.avgpool(feat_map)
        x = torch.flatten(x, 1)
        return self.dropout(x), feat_map

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        h, feat_map = self.encode(x)
        out: dict[str, torch.Tensor] = {
            "dr": self.dr_head(h),
            "glaucoma": self.gl_head(h).squeeze(-1),
            "amd": self.amd_head(h).squeeze(-1),
            "myopia": self.myo_head(h).squeeze(-1),
            "multidisease": self.multi_head(h),
        }
        if self.seg_head_enabled:
            seg_logits = self.seg_head(feat_map)
            out["seg"] = seg_logits
            out["cdr"] = cdr_from_seg_logits(seg_logits)
        return out

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
    disc_cup_mask: torch.Tensor | None = None
    mask_seg: torch.Tensor | None = None


class V10Dataset(Dataset):
    """통합 manifest — available_labels, 결측은 NaN."""

    def __init__(
        self,
        entries: list[dict],
        data_dir: Path,
        *,
        dr_data_dir: Path | None = None,
        class_names: tuple[str, ...] = MULTIDISEASE_TRAIN_CLASSES,
        image_size: int = 224,
        preprocess: str = "clahe",
        augment: bool = False,
    ) -> None:
        self.entries = entries
        self.data_dir = data_dir
        self.dr_data_dir = dr_data_dir
        self.class_names = class_names
        self.image_size = image_size
        self.preprocess = preprocess
        self.augment = augment

    def __len__(self) -> int:
        return len(self.entries)

    def _resolve_image_path(self, rel_path: str) -> Path:
        key = rel_path.replace("\\", "/")
        if key.startswith("/"):
            return Path(key)
        if self.dr_data_dir and (
            key.startswith("resized_cache/")
            or "/resized_cache/" in key
            or key.startswith("data/")
        ):
            return self.dr_data_dir / key.lstrip("/")
        return self.data_dir / key

    def _preprocess_mode_for(self, path: str) -> str:
        if "resized_cache" in path.replace("\\", "/"):
            return "none"
        return self.preprocess

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, dict[str, float | dict[str, float] | None]]:
        from PIL import Image
        from torchvision import transforms as T

        entry = self.entries[idx]
        al = entry.get("available_labels") or {}
        img_path = self._resolve_image_path(str(entry["path"]))
        img = Image.open(img_path).convert("RGB")
        arr = preprocess_fundus_array(
            __import__("numpy").array(img),
            mode=self._preprocess_mode_for(str(entry["path"])),
        )
        img = Image.fromarray(arr).resize((self.image_size, self.image_size))
        if self.augment:
            img = T.RandomHorizontalFlip()(img)
            img = T.ColorJitter(0.15, 0.15, 0.1)(img)
            if "glaucoma" in al:
                gl_transform = T.Compose(
                    [
                        T.RandomRotation(degrees=20),
                        T.RandomAffine(degrees=0, translate=(0.05, 0.05)),
                        T.RandomAutocontrast(p=0.3),
                    ]
                )
                img = gl_transform(img)
            img = T.ToTensor()(img)
        else:
            img = T.ToTensor()(img)
        labels: dict[str, float | dict[str, float] | None | torch.Tensor] = {
            "dr": float(al["dr"]) if "dr" in al else math.nan,
            "glaucoma": float(al["glaucoma"]) if "glaucoma" in al else math.nan,
            "amd": float(al["amd"]) if "amd" in al else math.nan,
            "myopia": float(al["myopia"]) if "myopia" in al else math.nan,
            "multidisease": dict(al["multidisease"]) if "multidisease" in al else None,
        }
        mask_rel = entry.get("disc_cup_mask")
        if mask_rel:
            import cv2

            mask_path = self.data_dir / str(mask_rel).replace("\\", "/")
            if mask_path.is_file():
                mask_arr = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
                if mask_arr is not None:
                    if mask_arr.shape != (self.image_size, self.image_size):
                        mask_arr = cv2.resize(
                            mask_arr,
                            (self.image_size, self.image_size),
                            interpolation=cv2.INTER_NEAREST,
                        )
                    labels["disc_cup_mask"] = torch.from_numpy(mask_arr.astype(np.int64))
                else:
                    labels["disc_cup_mask"] = torch.full(
                        (self.image_size, self.image_size),
                        SEG_IGNORE_INDEX,
                        dtype=torch.int64,
                    )
            else:
                labels["disc_cup_mask"] = torch.full(
                    (self.image_size, self.image_size),
                    SEG_IGNORE_INDEX,
                    dtype=torch.int64,
                )
        else:
            labels["disc_cup_mask"] = torch.full(
                (self.image_size, self.image_size),
                SEG_IGNORE_INDEX,
                dtype=torch.int64,
            )
        return img, labels


def _collate_v10(batch: list) -> tuple[torch.Tensor, V10BatchLabels]:
    imgs = torch.stack([b[0] for b in batch])
    n = len(batch)
    image_size = imgs.shape[-1]
    dr = torch.full((n,), float("nan"))
    gl = torch.full((n,), float("nan"))
    amd = torch.full((n,), float("nan"))
    myo = torch.full((n,), float("nan"))
    multi = torch.full((n, MULTI_NUM_CLASSES), float("nan"))
    seg_masks = torch.full((n, image_size, image_size), SEG_IGNORE_INDEX, dtype=torch.long)

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
        seg_t = labels.get("disc_cup_mask")
        if isinstance(seg_t, torch.Tensor):
            seg_masks[i] = seg_t.long()

    mask_seg = seg_masks.ne(SEG_IGNORE_INDEX).any(dim=(1, 2))

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
        disc_cup_mask=seg_masks,
        mask_seg=mask_seg,
    )


def _v10_labels_to_device(lb: V10BatchLabels, device: torch.device) -> V10BatchLabels:
    return V10BatchLabels(
        dr=lb.dr.to(device),
        glaucoma=lb.glaucoma.to(device),
        amd=lb.amd.to(device),
        myopia=lb.myopia.to(device),
        multidisease=lb.multidisease.to(device),
        mask_dr=lb.mask_dr.to(device),
        mask_gl=lb.mask_gl.to(device),
        mask_amd=lb.mask_amd.to(device),
        mask_myo=lb.mask_myo.to(device),
        mask_multi=lb.mask_multi.to(device),
        disc_cup_mask=lb.disc_cup_mask.to(device) if lb.disc_cup_mask is not None else None,
        mask_seg=lb.mask_seg.to(device) if lb.mask_seg is not None else None,
    )


class V10Loss(nn.Module):
    """마스킹 기반 5-head weighted loss (+ optional seg CE)."""

    def __init__(
        self,
        *,
        loss_weights: dict[str, float] | None = None,
        multi_pos_weight: torch.Tensor | None = None,
        focal_gamma: float = 2.0,
        seg_weight: float = 0.0,
    ) -> None:
        super().__init__()
        self.loss_weights = loss_weights or dict(LOSS_WEIGHTS)
        self.seg_weight = seg_weight
        self.focal = FocalLoss(gamma=focal_gamma)
        self.multi_criterion = nn.BCEWithLogitsLoss(
            pos_weight=multi_pos_weight,
            reduction="none",
        )
        self.seg_criterion = nn.CrossEntropyLoss(ignore_index=SEG_IGNORE_INDEX)

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

        if (
            self.seg_weight > 0
            and "seg" in outputs
            and labels.mask_seg is not None
            and labels.disc_cup_mask is not None
            and labels.mask_seg.any()
        ):
            seg_logits = outputs["seg"][labels.mask_seg]
            seg_targets = labels.disc_cup_mask[labels.mask_seg]
            parts["seg"] = self.seg_criterion(seg_logits, seg_targets)

        if not parts:
            zero = outputs["dr"].sum() * 0.0
            return zero, {}

        total = sum(self.loss_weights.get(k, 0.0) * v for k, v in parts.items() if k != "seg")
        if "seg" in parts:
            total = total + self.seg_weight * parts["seg"]
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
        xb = xb.to(device)
        lb = _v10_labels_to_device(lb, device)
        mask = lb.mask_dr
        if not mask.any():
            continue
        logits = model.forward(xb[mask])["dr"]
        ps.extend(logits.argmax(dim=1).cpu().tolist())
        ys.extend(lb.dr[mask].cpu().tolist())
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
        xb = xb.to(device)
        lb = _v10_labels_to_device(lb, device)
        if task == "glaucoma":
            mask = lb.mask_gl
            targets = lb.glaucoma
        elif task == "amd":
            mask = lb.mask_amd
            targets = lb.amd
        else:
            mask = lb.mask_myo
            targets = lb.myopia
        if not mask.any():
            continue
        logits = model.forward(xb[mask])[task]
        scores.extend(torch.sigmoid(logits).cpu().tolist())
        ys.extend(targets[mask].cpu().tolist())
    if len(set(int(y) for y in ys)) < 2:
        return 0.0
    return float(roc_auc_score(ys, scores))


def eval_gl_auc(model: MultiTaskV10Model, loader: DataLoader, device: torch.device) -> float:
    return eval_binary_auc(model, loader, device, "glaucoma")


def eval_amd_auc(model: MultiTaskV10Model, loader: DataLoader, device: torch.device) -> float:
    return eval_binary_auc(model, loader, device, "amd")


def eval_myo_auc(model: MultiTaskV10Model, loader: DataLoader, device: torch.device) -> float:
    return eval_binary_auc(model, loader, device, "myopia")


@torch.no_grad()
def eval_seg_dice(
    model: MultiTaskV10Model,
    loader: DataLoader,
    device: torch.device,
) -> float:
    if not getattr(model, "seg_head_enabled", False):
        return 0.0
    dices: list[float] = []
    for xb, lb in loader:
        xb = xb.to(device)
        lb = _v10_labels_to_device(lb, device)
        if lb.mask_seg is None or lb.disc_cup_mask is None or not lb.mask_seg.any():
            continue
        seg_logits = model.forward(xb)["seg"]
        pred = seg_logits.argmax(dim=1)
        for i in range(pred.shape[0]):
            if not lb.mask_seg[i]:
                continue
            tgt = lb.disc_cup_mask[i]
            valid = tgt.ge(0)
            if not valid.any():
                continue
            p = pred[i][valid]
            t = tgt[valid]
            inter = (p == t).float().sum()
            dice = (2.0 * inter) / (p.numel() + t.numel())
            dices.append(float(dice))
    return float(np.mean(dices)) if dices else 0.0


def composite_score(
    *,
    qwk: float,
    gl_auc: float,
    amd_auc: float,
    myo_auc: float,
    mauc: float,
    seg_dice: float = 0.0,
    loss_weights: dict[str, float] | None = None,
    seg_composite_weight: float = 0.0,
) -> float:
    w = loss_weights or LOSS_WEIGHTS
    base = (
        qwk * w["dr"]
        + gl_auc * w["glaucoma"]
        + amd_auc * w["amd"]
        + myo_auc * w["myopia"]
        + mauc * w["multidisease"]
    )
    if seg_composite_weight > 0:
        scale = max(1.0 - seg_composite_weight, 0.0)
        return base * scale + seg_dice * seg_composite_weight
    return base


@torch.no_grad()
def eval_multidisease_mauc(
    model: MultiTaskV10Model,
    loader: DataLoader,
    device: torch.device,
) -> float:
    import numpy as np
    from sklearn.metrics import roc_auc_score

    model.eval()
    all_scores: list[list[float]] = []
    all_targets: list[list[float]] = []

    for xb, lb in loader:
        xb = xb.to(device)
        lb = _v10_labels_to_device(lb, device)
        mask = lb.mask_multi
        if mask.sum() == 0:
            continue
        outputs = model.forward(xb[mask])
        logits = outputs["multidisease"]
        scores = torch.sigmoid(logits).cpu().tolist()
        targets = lb.multidisease[mask].cpu().tolist()
        all_scores.extend(scores)
        all_targets.extend(targets)

    if not all_scores:
        return 0.0

    scores_arr = np.array(all_scores, dtype=np.float64)
    targets_arr = np.array(all_targets, dtype=np.float64)
    aucs: list[float] = []
    for i in range(scores_arr.shape[1]):
        yt = targets_arr[:, i]
        ys = scores_arr[:, i]
        if yt.sum() > 0 and (1.0 - yt).sum() > 0:
            aucs.append(float(roc_auc_score(yt, ys)))
    return float(np.mean(aucs)) if aucs else 0.0


def main() -> None:
    p = argparse.ArgumentParser(description="v10 unified multitask training")
    p.add_argument("--manifest", type=Path, default=ROOT / "training/manifests/unified_v10.json")
    p.add_argument("--pretrained", type=Path, default=ROOT / "models/retinal_v4.pt")
    p.add_argument("--output", type=Path, default=ROOT / "models/retinal_v10")
    p.add_argument("--epochs", type=int, default=60)
    p.add_argument("--batch-size", dest="batch_size", type=int, default=128)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--finetune-lr", dest="finetune_lr", type=float, default=1e-5)
    p.add_argument("--warmup-epochs", dest="warmup_epochs", type=int, default=WARMUP_EPOCHS)
    p.add_argument("--image-size", dest="image_size", type=int, default=224)
    p.add_argument("--device", default="cuda")
    p.add_argument("--early-stop", dest="early_stop", type=int, default=12)
    p.add_argument("--no-amp", action="store_true")
    p.add_argument("--dr-weight", dest="dr_weight", type=float, default=LOSS_WEIGHTS["dr"])
    p.add_argument("--gl-weight", dest="gl_weight", type=float, default=LOSS_WEIGHTS["glaucoma"])
    p.add_argument("--amd-weight", dest="amd_weight", type=float, default=LOSS_WEIGHTS["amd"])
    p.add_argument("--myo-weight", dest="myo_weight", type=float, default=LOSS_WEIGHTS["myopia"])
    p.add_argument("--multi-weight", dest="multi_weight", type=float, default=LOSS_WEIGHTS["multidisease"])
    p.add_argument(
        "--gl-oversample",
        dest="gl_oversample",
        type=float,
        default=1.0,
        help="GL 샘플 WeightedRandomSampler 가중치 배율 (기본 1.0)",
    )
    p.add_argument("--seg-head", dest="seg_head", action="store_true")
    p.add_argument("--seg-weight", dest="seg_weight", type=float, default=SEG_LOSS_WEIGHT)
    p.add_argument(
        "--seg-composite-weight",
        dest="seg_composite_weight",
        type=float,
        default=SEG_COMPOSITE_WEIGHT,
    )
    p.add_argument("--smoke", action="store_true", help="소량 샘플 1 epoch smoke test")
    args = p.parse_args()

    loss_weights = {
        "dr": args.dr_weight,
        "glaucoma": args.gl_weight,
        "amd": args.amd_weight,
        "myopia": args.myo_weight,
        "multidisease": args.multi_weight,
    }
    weight_sum = sum(loss_weights.values())
    if abs(weight_sum - 1.0) > 0.05:
        print(f"WARN: loss weight sum={weight_sum:.3f} (expected ~1.0)")

    manifest_path = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    train_entries, val_entries, _ = _manifest_splits(data)
    if args.smoke:
        # 마스크 보유 샘플을 우선 포함 (seg_head smoke test 검증용)
        train_masked = [e for e in train_entries if e.get("disc_cup_mask")]
        train_rest = [e for e in train_entries if not e.get("disc_cup_mask")]
        train_entries = (train_masked[:16] + train_rest)[:64]
        val_masked = [e for e in val_entries if e.get("disc_cup_mask")]
        val_rest = [e for e in val_entries if not e.get("disc_cup_mask")]
        val_entries = (val_masked[:8] + val_rest)[:32]
        n_mask_tr = sum(1 for e in train_entries if e.get("disc_cup_mask"))
        n_mask_val = sum(1 for e in val_entries if e.get("disc_cup_mask"))
        print(f"smoke: train={len(train_entries)}(mask={n_mask_tr}) val={len(val_entries)}(mask={n_mask_val})")
    data_dir = _resolve_data_dir(str(data.get("data_dir") or "/dataset"))
    dr_raw = data.get("dr_data_dir")
    dr_data_dir = Path(str(dr_raw)) if dr_raw else None
    preprocess = resolve_preprocess_mode("none")

    use_cuda = args.device == "cuda" and torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")
    use_amp = use_cuda and not args.no_amp

    train_ds = V10Dataset(
        train_entries,
        data_dir,
        dr_data_dir=dr_data_dir,
        image_size=args.image_size,
        preprocess=preprocess,
        augment=True,
    )
    val_ds = V10Dataset(
        val_entries,
        data_dir,
        dr_data_dir=dr_data_dir,
        image_size=args.image_size,
        preprocess=preprocess,
        augment=False,
    )
    train_sampler = None
    train_shuffle = True
    if args.gl_oversample > 1.0:
        sample_weights = []
        for entry in train_entries:
            labels = entry.get("available_labels") or {}
            if "glaucoma" in labels:
                sample_weights.append(float(args.gl_oversample))
            else:
                sample_weights.append(1.0)
        train_sampler = WeightedRandomSampler(
            weights=sample_weights,
            num_samples=len(train_entries),
            replacement=True,
        )
        train_shuffle = False
        print(f"GL oversample: {args.gl_oversample}x ({sum(1 for e in train_entries if 'glaucoma' in (e.get('available_labels') or {}))} GL samples)")

    train_loader = DataLoader(
        train_ds,
        batch_size=args.batch_size,
        shuffle=train_shuffle,
        sampler=train_sampler,
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
    model = MultiTaskV10Model(
        pretrained_imagenet=not pretrained.is_file(),
        seg_head=args.seg_head,
        image_size=args.image_size,
    )
    if pretrained.is_file():
        load_v4_into_v10(model, pretrained)
    model.to(device)

    criterion = V10Loss(loss_weights=loss_weights, seg_weight=args.seg_weight if args.seg_head else 0.0)
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
        f"device={device} amp={use_amp} warmup={args.warmup_epochs} "
        f"seg_head={args.seg_head}"
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
            lb = _v10_labels_to_device(lb, device)
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
        gl_auc = eval_gl_auc(model, val_loader, device)
        amd_auc = eval_amd_auc(model, val_loader, device)
        myo_auc = eval_myo_auc(model, val_loader, device)
        mauc = eval_multidisease_mauc(model, val_loader, device)
        seg_dice = eval_seg_dice(model, val_loader, device) if args.seg_head else 0.0
        composite = composite_score(
            qwk=qwk,
            gl_auc=gl_auc,
            amd_auc=amd_auc,
            myo_auc=myo_auc,
            mauc=mauc,
            seg_dice=seg_dice,
            loss_weights=loss_weights,
            seg_composite_weight=args.seg_composite_weight if args.seg_head else 0.0,
        )

        seg_msg = f" segDice={seg_dice:.4f}" if args.seg_head else ""
        print(
            f"epoch {epoch}/{args.epochs} loss={running/max(len(train_loader),1):.4f} "
            f"QWK={qwk:.4f} GL={gl_auc:.4f} AMD={amd_auc:.4f} MYO={myo_auc:.4f} "
            f"mAUC={mauc:.4f}{seg_msg} composite={composite:.4f}"
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

    arch = "efficientnet_b4_v12" if args.seg_head else "efficientnet_b4_v10"
    torch.save(
        {
            "model_state": model.state_dict(),
            "arch": arch,
            "best_composite": best_score,
            "loss_weights": loss_weights,
            "seg_head": args.seg_head,
            "seg_weight": args.seg_weight if args.seg_head else 0.0,
        },
        best_pt,
    )
    meta = {
        "arch": arch,
        "manifest": manifest_path.name,
        "preprocess": preprocess,
        "image_size": args.image_size,
        "best_composite": round(best_score, 4),
        "loss_weights": loss_weights,
        "warmup_epochs": args.warmup_epochs,
        "seg_head": args.seg_head,
        "seg_weight": args.seg_weight if args.seg_head else 0.0,
    }
    (out_dir / "best.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"OK {best_pt} composite={best_score:.4f}")


if __name__ == "__main__":
    main()
