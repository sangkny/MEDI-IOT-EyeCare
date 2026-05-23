#!/usr/bin/env python3
"""MEDI DR CNN 독립 훈련 스크립트 (EfficientNet / MSEF-Net).

기능:
  - CLAHE / Ben Graham 전처리 (services.retinal_cnn SSOT)
  - Mixed Precision (CUDA 시 자동)
  - WeightedRandomSampler (클래스 불균형)
  - Early stopping (val QWK) + CosineAnnealingLR
  - ONNX + meta.json 자동 생성

예:
  python training/train.py --manifest data/synthetic_manifest.json --arch efficientnet_b4
  python training/train.py --manifest data/messidor2_manifest.json --epochs 50 --device cuda
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
    DR_NUM_CLASSES,
    build_dr_classifier,
    preprocess_fundus_array,
    resolve_cnn_arch,
    resolve_preprocess_mode,
)


class FundusManifestDataset(Dataset):
    def __init__(
        self,
        entries: list[dict],
        data_dir: Path,
        *,
        image_size: int,
        preprocess: str,
        augment: bool,
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
        path = self.data_dir / e["path"]
        grade = int(e["dr_grade"])
        img = Image.open(path).convert("RGB")
        arr = preprocess_fundus_array(
            __import__("numpy").array(img), mode=self.preprocess
        )
        img = Image.fromarray(arr).resize((self.image_size, self.image_size))
        if self.augment:
            t = T.Compose(
                [
                    T.RandomHorizontalFlip(),
                    T.RandomRotation(15),
                    T.ColorJitter(0.15, 0.15, 0.1),
                    T.ToTensor(),
                ]
            )
        else:
            t = T.ToTensor()
        return t(img), grade


def _class_weights(entries: list[dict]) -> torch.Tensor:
    counts = Counter(int(e["dr_grade"]) for e in entries)
    total = sum(counts.values())
    weights = [total / (DR_NUM_CLASSES * counts.get(g, 1)) for g in range(DR_NUM_CLASSES)]
    return torch.tensor(weights, dtype=torch.float32)


def _sample_weights(entries: list[dict]) -> list[float]:
    counts = Counter(int(e["dr_grade"]) for e in entries)
    total = len(entries)
    return [total / (DR_NUM_CLASSES * counts[e["dr_grade"]]) for e in entries]


def quadratic_weighted_kappa(y_true, y_pred) -> float:
    from sklearn.metrics import cohen_kappa_score

    return float(cohen_kappa_score(y_true, y_pred, weights="quadratic"))


@torch.no_grad()
def evaluate_model(model, loader, device) -> tuple[float, float]:
    model.eval()
    ys, ps = [], []
    correct = total = 0
    for xb, yb in loader:
        xb, yb = xb.to(device), yb.to(device)
        logits = model(xb)
        pred = logits.argmax(dim=1)
        correct += (pred == yb).sum().item()
        total += yb.size(0)
        ys.extend(yb.cpu().tolist())
        ps.extend(pred.cpu().tolist())
    acc = correct / max(total, 1)
    qwk = quadratic_weighted_kappa(ys, ps) if ys else 0.0
    return qwk, acc


def export_onnx(model, path: Path, image_size: int) -> None:
    model.eval()
    cpu_model = model.cpu()
    dummy = torch.randn(1, 3, image_size, image_size)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        cpu_model,
        dummy,
        str(path),
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={"input": {0: "batch"}, "output": {0: "batch"}},
        opset_version=17,
    )


def main() -> None:
    p = argparse.ArgumentParser(description="MEDI DR CNN training")
    p.add_argument("--arch", default="efficientnet_b4")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--preprocess", default="clahe", choices=["none", "clahe", "ben_graham", "both"])
    p.add_argument("--epochs", type=int, default=30)
    p.add_argument("--batch-size", dest="batch_size", type=int, default=16)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--image-size", dest="image_size", type=int, default=224)
    p.add_argument("--output", type=Path, default=ROOT / "models" / "retinal_v3.pt")
    p.add_argument("--device", default="cuda")
    p.add_argument("--early-stop", dest="early_stop", type=int, default=5)
    p.add_argument("--skip-onnx", action="store_true")
    p.add_argument("--no-amp", action="store_true", help="Mixed precision 비활성")
    p.add_argument("--no-pretrained", action="store_true")
    p.add_argument("--smoke", action="store_true")
    args = p.parse_args()

    if args.smoke:
        args.epochs = 1
        args.batch_size = 4
        args.image_size = 64

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

    print(
        f"device={device} amp={use_amp} arch={args.arch} "
        f"train={len(train_entries)} val={len(val_entries)}"
    )

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

    model, arch_key = build_dr_classifier(
        arch=args.arch, pretrained=not args.no_pretrained and not args.smoke
    )
    model.to(device)
    loss_fn = nn.CrossEntropyLoss(weight=_class_weights(train_entries).to(device))
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(args.epochs, 1))
    scaler = torch.cuda.amp.GradScaler(enabled=use_amp)

    best_qwk = -1.0
    best_state = None
    stale = 0

    for epoch in range(1, args.epochs + 1):
        model.train()
        running = 0.0
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad(set_to_none=True)
            with torch.cuda.amp.autocast(enabled=use_amp):
                loss = loss_fn(model(xb), yb)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            running += loss.item()
        scheduler.step()
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
            print(f"early_stop patience={args.early_stop}")
            break

    if best_state:
        model.load_state_dict(best_state)

    out_pt = args.output if args.output.is_absolute() else ROOT / args.output
    out_pt.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "state_dict": model.state_dict(),
            "arch": arch_key,
            "preprocess": preprocess,
            "image_size": args.image_size,
            "best_val_qwk": best_qwk,
        },
        out_pt,
    )
    print(f"OK checkpoint {out_pt} best_val_qwk={best_qwk:.4f}")

    if not args.skip_onnx:
        onnx_path = out_pt.with_suffix(".onnx")
        export_onnx(model, onnx_path, args.image_size)
        print(f"OK onnx {onnx_path}")

    meta = {
        "arch": arch_key,
        "preprocess": preprocess,
        "image_size": args.image_size,
        "onnx": out_pt.with_suffix(".onnx").name,
        "pt": out_pt.name,
        "version": "train-kit-v1",
        "trained_on": manifest_path.name,
        "epochs": args.epochs,
        "qwk": round(best_qwk, 4),
    }
    meta_path = out_pt.with_name(out_pt.stem + ".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK meta {meta_path}")


if __name__ == "__main__":
    main()
