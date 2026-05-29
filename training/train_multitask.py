#!/usr/bin/env python3
"""멀티태스크 안저 진단 훈련 (DR + Glaucoma + AMD + Myopia).

공유 백본 + 질환별 분류 헤드. Phase 1~3 로드맵용 SSOT.

예:
  python training/train_multitask.py \\
    --manifest training/manifests/multi_indication.json \\
    --tasks dr,glaucoma \\
    --backbone efficientnet_b4 \\
    --epochs 30 --output models/multitask_v1.pt
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler

from services.retinal_cnn import (
    _load_efficientnet_backbone,
    preprocess_fundus_array,
    resolve_preprocess_mode,
)
from training.train import export_onnx

TASK_NUM_CLASSES: dict[str, int] = {
    "dr": 5,
    "glaucoma": 3,
    "amd": 4,
    "myopia": 4,
}

TASK_LABEL_KEYS: dict[str, str] = {
    "dr": "dr_grade",
    "glaucoma": "glaucoma_grade",
    "amd": "amd_grade",
    "myopia": "myopia_grade",
}

TASK_WEIGHTS: dict[str, float] = {
    "dr": 1.0,
    "glaucoma": 0.8,
    "amd": 0.8,
    "myopia": 0.6,
}

SUPPORTED_BACKBONES = ("efficientnet_b4", "efficientnet_b0", "retfound")


class EfficientNetFeatureBackbone(nn.Module):
    """EfficientNet feature extractor (classifier 제거)."""

    def __init__(self, arch: str = "efficientnet_b4", *, pretrained: bool = False) -> None:
        super().__init__()
        self.arch = arch
        backbone = _load_efficientnet_backbone(arch, pretrained=pretrained)
        self.features = backbone.features
        self.avgpool = backbone.avgpool
        self.num_features = backbone.classifier[1].in_features

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = self.avgpool(x)
        return torch.flatten(x, 1)


class RETFoundFeatureBackbone(nn.Module):
    """RETFound / ViT-Large feature extractor (num_classes=0)."""

    def __init__(self, pretrained_path: Path | None = None) -> None:
        super().__init__()
        import timm

        self.model = timm.create_model(
            "vit_large_patch16_224",
            pretrained=pretrained_path is None,
            num_classes=0,
        )
        self.num_features = self.model.num_features
        if pretrained_path and pretrained_path.is_file():
            ckpt = torch.load(pretrained_path, map_location="cpu", weights_only=False)
            if isinstance(ckpt, dict) and "model" in ckpt:
                state = ckpt["model"]
            elif isinstance(ckpt, dict) and "state_dict" in ckpt:
                state = ckpt["state_dict"]
            else:
                state = ckpt
            missing, unexpected = self.model.load_state_dict(state, strict=False)
            print(
                f"RETFound backbone: {pretrained_path.name} "
                f"missing={len(missing)} unexpected={len(unexpected)}"
            )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.model(x)


def build_backbone(
    backbone: str,
    *,
    pretrained: bool = False,
    retfound_pretrained: Path | None = None,
) -> nn.Module:
    key = backbone.lower()
    if key in ("efficientnet_b4", "efficientnet_b0", "efficientnet_v2_s"):
        return EfficientNetFeatureBackbone(key, pretrained=pretrained)
    if key in ("retfound", "vit_large_retfound"):
        return RETFoundFeatureBackbone(retfound_pretrained)
    raise ValueError(f"unsupported backbone={backbone!r}; choose from {SUPPORTED_BACKBONES}")


class MultiTaskEyeCareModel(nn.Module):
    """
    단일 안저 이미지 → 다중 질환 동시 진단
    공유 백본 + 질환별 분류 헤드

    지원 태스크:
      dr:       당뇨망막병증 0~4등급
      glaucoma: 정상/의심/확진 3등급
      amd:      정상/초기/중기/말기 4등급
      myopia:   정상/경도/중등도/고도 4등급
    """

    def __init__(
        self,
        backbone: str = "efficientnet_b4",
        tasks: list[str] | None = None,
        *,
        pretrained: bool = False,
        retfound_pretrained: Path | None = None,
    ) -> None:
        super().__init__()
        self.tasks = tasks or ["dr", "glaucoma", "amd"]
        for task in self.tasks:
            if task not in TASK_NUM_CLASSES:
                raise ValueError(f"unknown task={task!r}")

        self.backbone = build_backbone(
            backbone,
            pretrained=pretrained,
            retfound_pretrained=retfound_pretrained,
        )
        feat_dim = self.backbone.num_features
        self.heads = nn.ModuleDict(
            {task: nn.Linear(feat_dim, TASK_NUM_CLASSES[task]) for task in self.tasks}
        )

    def forward(
        self,
        x: torch.Tensor,
        task: str | None = None,
    ) -> torch.Tensor | dict[str, torch.Tensor]:
        feat = self.backbone(x)
        if task:
            if task not in self.heads:
                raise KeyError(f"task {task!r} not in {list(self.heads.keys())}")
            return self.heads[task](feat)
        return {t: h(feat) for t, h in self.heads.items()}


class MultiTaskManifestDataset(Dataset):
    """manifest 항목에서 활성 태스크 라벨만 추출 (없으면 -1)."""

    def __init__(
        self,
        entries: list[dict],
        data_dir: Path,
        tasks: list[str],
        *,
        image_size: int,
        preprocess: str,
        augment: bool,
    ) -> None:
        self.entries = entries
        self.data_dir = data_dir
        self.tasks = tasks
        self.image_size = image_size
        self.preprocess = preprocess
        self.augment = augment

    def __len__(self) -> int:
        return len(self.entries)

    def __getitem__(self, idx: int):
        from PIL import Image
        from torchvision import transforms as T

        entry = self.entries[idx]
        path = self.data_dir / entry["path"]
        img = Image.open(path).convert("RGB")
        arr = preprocess_fundus_array(__import__("numpy").array(img), mode=self.preprocess)
        img = Image.fromarray(arr).resize((self.image_size, self.image_size))
        if self.augment:
            transform = T.Compose(
                [
                    T.RandomHorizontalFlip(),
                    T.RandomRotation(15),
                    T.ColorJitter(0.15, 0.15, 0.1),
                    T.ToTensor(),
                ]
            )
        else:
            transform = T.ToTensor()

        labels = {}
        for task in self.tasks:
            key = TASK_LABEL_KEYS[task]
            labels[task] = int(entry[key]) if key in entry and entry[key] is not None else -1
        return transform(img), labels


def _sample_weights(entries: list[dict], primary_task: str) -> list[float]:
    key = TASK_LABEL_KEYS[primary_task]
    labeled = [e for e in entries if key in e and e[key] is not None]
    if not labeled:
        return [1.0] * len(entries)
    counts = Counter(int(e[key]) for e in labeled)
    n_classes = TASK_NUM_CLASSES[primary_task]
    total = len(labeled)
    weight_by_grade = {g: total / (n_classes * counts.get(g, 1)) for g in range(n_classes)}
    default = total / max(len(labeled), 1)
    return [
        weight_by_grade.get(int(e[key]), default) if key in e and e[key] is not None else default
        for e in entries
    ]


def _task_criterion(entries: list[dict], task: str, device: torch.device) -> nn.CrossEntropyLoss:
    key = TASK_LABEL_KEYS[task]
    labeled = [e for e in entries if key in e and e[key] is not None]
    n_classes = TASK_NUM_CLASSES[task]
    if not labeled:
        return nn.CrossEntropyLoss(ignore_index=-1)
    counts = Counter(int(e[key]) for e in labeled)
    total = sum(counts.values())
    weights = [total / (n_classes * counts.get(g, 1)) for g in range(n_classes)]
    return nn.CrossEntropyLoss(weight=torch.tensor(weights, dtype=torch.float32, device=device))


def _compute_task_loss(
    preds: dict[str, torch.Tensor],
    labels: dict[str, list[int]],
    criteria: dict[str, nn.CrossEntropyLoss],
    active_tasks: list[str],
) -> tuple[torch.Tensor, dict[str, float]]:
    total = torch.tensor(0.0, device=next(iter(preds.values())).device)
    parts: dict[str, float] = {}
    for task in active_tasks:
        y = torch.tensor(labels[task], device=total.device, dtype=torch.long)
        mask = y >= 0
        if mask.sum().item() == 0:
            continue
        loss = criteria[task](preds[task][mask], y[mask])
        weighted = TASK_WEIGHTS[task] * loss
        total = total + weighted
        parts[task] = float(loss.item())
    return total, parts


@torch.no_grad()
def evaluate_multitask(
    model: MultiTaskEyeCareModel,
    loader: DataLoader,
    device: torch.device,
    tasks: list[str],
) -> dict[str, float]:
    from sklearn.metrics import roc_auc_score

    model.eval()
    metrics: dict[str, float] = {}
    collected: dict[str, tuple[list[int], list[int]]] = {t: ([], []) for t in tasks}

    for xb, label_dict in loader:
        xb = xb.to(device)
        preds = model(xb)
        for task in tasks:
            ys = label_dict[task]
            if isinstance(ys, torch.Tensor):
                y_list = ys.tolist()
            else:
                y_list = ys
            pred = preds[task].argmax(dim=1).cpu().tolist()
            for yi, pi in zip(y_list, pred):
                yi_int = int(yi)
                if yi_int < 0:
                    continue
                collected[task][0].append(yi_int)
                collected[task][1].append(int(pi))

    for task in tasks:
        y_true, y_pred = collected[task]
        if not y_true:
            metrics[f"{task}_acc"] = 0.0
            metrics[f"{task}_auc"] = 0.0
            continue
        acc = sum(a == b for a, b in zip(y_true, y_pred)) / len(y_true)
        metrics[f"{task}_acc"] = acc
        if len(set(y_true)) > 1 and TASK_NUM_CLASSES[task] == 2:
            try:
                metrics[f"{task}_auc"] = float(roc_auc_score(y_true, y_pred))
            except ValueError:
                metrics[f"{task}_auc"] = 0.0
        else:
            metrics[f"{task}_auc"] = acc
    return metrics


def count_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


class _ExportPrimaryHead(nn.Module):
    """ONNX export — primary task head only."""

    def __init__(self, model: MultiTaskEyeCareModel, task: str) -> None:
        super().__init__()
        self.model = model
        self.task = task

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.model(x, task=self.task)


def main() -> None:
    parser = argparse.ArgumentParser(description="MEDI multi-task fundus training")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--backbone", default="efficientnet_b4", choices=list(SUPPORTED_BACKBONES))
    parser.add_argument("--tasks", default="dr,glaucoma,amd", help="쉼표 구분 태스크 목록")
    parser.add_argument("--preprocess", default="clahe", choices=["none", "clahe", "ben_graham", "both"])
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", dest="batch_size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--image-size", dest="image_size", type=int, default=224)
    parser.add_argument("--output", type=Path, default=ROOT / "models" / "multitask_v1.pt")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--early-stop", dest="early_stop", type=int, default=5)
    parser.add_argument("--skip-onnx", action="store_true")
    parser.add_argument("--no-amp", action="store_true")
    parser.add_argument("--no-pretrained", action="store_true")
    parser.add_argument(
        "--retfound-pretrained",
        type=Path,
        default=ROOT / "models" / "pretrained" / "RETFound_mae_natureCFP.pth",
    )
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    if args.smoke:
        args.epochs = 1
        args.batch_size = 4
        args.image_size = 64

    tasks = [t.strip() for t in args.tasks.split(",") if t.strip()]
    manifest_path = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data_dir = Path(data["data_dir"])
    train_entries = data.get("train") or []
    val_entries = data.get("val") or data.get("test") or []
    if not train_entries:
        raise SystemExit("manifest train split empty")

    preprocess = resolve_preprocess_mode(args.preprocess)
    use_cuda = args.device == "cuda" and torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")
    use_amp = use_cuda and not args.no_amp

    model = MultiTaskEyeCareModel(
        backbone=args.backbone,
        tasks=tasks,
        pretrained=not args.no_pretrained and not args.smoke,
        retfound_pretrained=args.retfound_pretrained,
    ).to(device)
    n_params = count_parameters(model)
    print(f"MultiTaskEyeCareModel params={n_params:,} tasks={tasks} backbone={args.backbone}")

    train_ds = MultiTaskManifestDataset(
        train_entries,
        data_dir,
        tasks,
        image_size=args.image_size,
        preprocess=preprocess,
        augment=True,
    )
    val_ds = MultiTaskManifestDataset(
        val_entries,
        data_dir,
        tasks,
        image_size=args.image_size,
        preprocess=preprocess,
        augment=False,
    )

    primary_task = tasks[0]
    sampler = WeightedRandomSampler(
        weights=_sample_weights(train_entries, primary_task),
        num_samples=len(train_entries),
        replacement=True,
    )
    train_loader = DataLoader(
        train_ds,
        batch_size=args.batch_size,
        sampler=sampler,
        num_workers=4,
        pin_memory=True,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=4,
        pin_memory=True,
    )

    criteria = {task: _task_criterion(train_entries, task, device) for task in tasks}
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(args.epochs, 1))
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)

    best_score = -1.0
    best_state = None
    stale = 0

    for epoch in range(1, args.epochs + 1):
        model.train()
        running = 0.0
        for xb, label_dict in train_loader:
            xb = xb.to(device)
            batch_labels = {
                task: (
                    label_dict[task].tolist()
                    if isinstance(label_dict[task], torch.Tensor)
                    else label_dict[task]
                )
                for task in tasks
            }
            optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast("cuda", enabled=use_amp):
                preds = model(xb)
                loss, _parts = _compute_task_loss(preds, batch_labels, criteria, tasks)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            running += float(loss.item())
        scheduler.step()

        val_metrics = evaluate_multitask(model, val_loader, device, tasks) if val_entries else {}
        score_key = f"{primary_task}_acc"
        val_score = val_metrics.get(score_key, 0.0)
        metric_str = " ".join(f"{k}={v:.4f}" for k, v in sorted(val_metrics.items()))
        print(
            f"epoch {epoch}/{args.epochs} loss={running / max(len(train_loader), 1):.4f} "
            f"val_score={val_score:.4f} {metric_str}"
        )

        if val_score > best_score:
            best_score = val_score
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            stale = 0
        else:
            stale += 1
        if args.early_stop and stale >= args.early_stop:
            print(f"early_stop patience={args.early_stop}")
            break

    if best_state:
        model.load_state_dict(best_state)

    out_pt = args.output if args.output.is_absolute() else ROOT / args.output
    out_pt.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state": model.state_dict(),
            "state_dict": model.state_dict(),
            "epoch": epoch,
            "best_score": best_score,
            "arch": args.backbone,
            "tasks": tasks,
            "preprocess": preprocess,
            "image_size": args.image_size,
            "num_params": n_params,
        },
        out_pt,
    )
    print(f"OK checkpoint {out_pt} best_score={best_score:.4f} params={n_params:,}")

    if not args.skip_onnx:
        export_head = _ExportPrimaryHead(model, tasks[0])
        export_onnx(export_head, out_pt.with_suffix(".onnx"), args.image_size)
        print(f"OK onnx {out_pt.with_suffix('.onnx')} (head={tasks[0]})")

    meta = {
        "arch": args.backbone,
        "tasks": tasks,
        "preprocess": preprocess,
        "image_size": args.image_size,
        "num_params": n_params,
        "trained_on": manifest_path.name,
        "best_score": round(best_score, 4),
    }
    meta_path = out_pt.with_name(out_pt.stem + ".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK meta {meta_path}")


if __name__ == "__main__":
    main()
