#!/usr/bin/env python3
"""
파일명: scripts/train_prognosis_mlp.py
목적:   Phase 1 예후 예측 MLP — v14/v15 backbone 임베딩 + 5-fold CV

IRB: 국내 임상기관 IRB 승인 (2019) — 로컬 전용
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from torch.utils.data import DataLoader, TensorDataset

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.retinal_cnn import preprocess_fundus_array
from training.train_v10 import MultiTaskV10Model

DEFAULT_PAIRS = Path("/dataset/korean_glaucoma_fundus/prognosis_pairs.csv")
DEFAULT_BACKBONE = ROOT / "models/retinal_v14/best.pt"
DEFAULT_OUTPUT = ROOT / "models/prognosis_v1"
FEAT_DIM = 1792
INPUT_DIM = FEAT_DIM * 2 + 3  # OD + OS + grade + is_ntg + days_norm


def _load_image_tensor(path: Path, image_size: int = 224) -> torch.Tensor:
    from PIL import Image
    from torchvision import transforms as T

    img = Image.open(path).convert("RGB")
    arr = preprocess_fundus_array(np.array(img), mode="clahe")
    img = Image.fromarray(arr).resize((image_size, image_size))
    t = T.Compose([T.ToTensor(), T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])(img)
    return t


class EmbeddingExtractor:
    """v14/v15 PyTorch backbone → 1792-d embedding (frozen)."""

    def __init__(
        self,
        checkpoint: Path,
        *,
        device: torch.device,
        image_size: int = 224,
    ) -> None:
        self.device = device
        self.image_size = image_size
        self.model = MultiTaskV10Model(pretrained_imagenet=False, grade_head=False)
        ckpt = torch.load(checkpoint, map_location="cpu", weights_only=True)
        if isinstance(ckpt, dict) and "model_state" in ckpt:
            self.model.load_state_dict(ckpt["model_state"], strict=False)
        else:
            raise ValueError(f"unsupported checkpoint format: {checkpoint}")
        self.model.eval()
        self.model.to(device)
        for p in self.model.parameters():
            p.requires_grad = False

    @torch.no_grad()
    def extract(self, path: Path) -> np.ndarray:
        if not path.is_file():
            raise FileNotFoundError(path)
        x = _load_image_tensor(path, self.image_size).unsqueeze(0).to(self.device)
        h, _ = self.model.encode(x)
        return h.squeeze(0).cpu().numpy().astype(np.float32)


class PrognosisMLP(nn.Module):
    def __init__(self, input_dim: int = INPUT_DIM, dropout: float = 0.3) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 512),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(512, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(128, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


@dataclass
class FoldMetrics:
    fold: int
    auc: float
    sensitivity: float
    specificity: float
    n_val: int


def _metrics(y_true: np.ndarray, y_prob: np.ndarray, threshold: float = 0.5) -> tuple[float, float, float]:
    if len(np.unique(y_true)) < 2:
        auc = 0.5
    else:
        auc = float(roc_auc_score(y_true, y_prob))
    pred = (y_prob >= threshold).astype(int)
    tp = int(((pred == 1) & (y_true == 1)).sum())
    fn = int(((pred == 0) & (y_true == 1)).sum())
    tn = int(((pred == 0) & (y_true == 0)).sum())
    fp = int(((pred == 1) & (y_true == 0)).sum())
    sens = tp / (tp + fn) if (tp + fn) else 0.0
    spec = tn / (tn + fp) if (tn + fp) else 0.0
    return auc, sens, spec


def build_feature_matrix(
    pairs: list[dict],
    extractor: EmbeddingExtractor,
) -> tuple[np.ndarray, np.ndarray]:
    xs: list[np.ndarray] = []
    ys: list[int] = []
    for i, row in enumerate(pairs):
        pr = Path(row["path_fundus_R_i"])
        pl = Path(row["path_fundus_L_i"])
        emb_r = extractor.extract(pr)
        emb_l = extractor.extract(pl)
        grade = float(row["grade_i"]) / 3.0
        is_ntg = float(row["is_ntg"])
        days = float(row["days_interval"]) / 365.0
        feat = np.concatenate([emb_r, emb_l, np.array([grade, is_ntg, days], dtype=np.float32)])
        xs.append(feat)
        ys.append(int(row["label"]))
        if (i + 1) % 10 == 0:
            print(f"  embedded {i + 1}/{len(pairs)}")
    return np.stack(xs), np.array(ys, dtype=np.float32)


def train_fold(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_val: np.ndarray,
    y_val: np.ndarray,
    *,
    device: torch.device,
    epochs: int,
    lr: float,
    pos_weight: float,
) -> tuple[PrognosisMLP, FoldMetrics]:
    model = PrognosisMLP().to(device)
    criterion = nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor([pos_weight], device=device),
    )
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-3)

    train_ds = TensorDataset(
        torch.from_numpy(x_train),
        torch.from_numpy(y_train),
    )
    loader = DataLoader(train_ds, batch_size=min(16, len(train_ds)), shuffle=True)

    for _ in range(epochs):
        model.train()
        for xb, yb in loader:
            xb = xb.to(device)
            yb = yb.to(device)
            opt.zero_grad(set_to_none=True)
            logits = model(xb)
            loss = criterion(logits, yb)
            loss.backward()
            opt.step()

    model.eval()
    with torch.no_grad():
        logits = model(torch.from_numpy(x_val).to(device))
        prob = torch.sigmoid(logits).cpu().numpy()

    auc, sens, spec = _metrics(y_val, prob)
    return model, FoldMetrics(fold=0, auc=auc, sensitivity=sens, specificity=spec, n_val=len(y_val))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--pairs-csv", type=Path, default=DEFAULT_PAIRS)
    p.add_argument("--backbone", type=Path, default=DEFAULT_BACKBONE)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--folds", type=int, default=5)
    p.add_argument("--epochs", type=int, default=80)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--device", default="cuda")
    p.add_argument("--smoke", action="store_true")
    args = p.parse_args()

    pairs_path = args.pairs_csv if args.pairs_csv.is_absolute() else ROOT / args.pairs_csv
    if not pairs_path.is_file():
        print(f"error: missing {pairs_path} — run build_prognosis_pairs.py", file=sys.stderr)
        sys.exit(1)

    pairs = list(csv.DictReader(open(pairs_path, encoding="utf-8")))
    if args.smoke:
        pairs = pairs[: min(12, len(pairs))]
        args.folds = min(3, args.folds)
        args.epochs = 5

    if len(pairs) < args.folds:
        print(f"error: need at least {args.folds} pairs, got {len(pairs)}", file=sys.stderr)
        sys.exit(1)

    use_cuda = args.device == "cuda" and torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")
    backbone = args.backbone if args.backbone.is_absolute() else ROOT / args.backbone
    if not backbone.is_file():
        print(f"error: backbone missing {backbone}", file=sys.stderr)
        sys.exit(1)

    print(f"extracting embeddings from {backbone.name} ({len(pairs)} pairs)...")
    extractor = EmbeddingExtractor(backbone, device=device)
    x_all, y_all = build_feature_matrix(pairs, extractor)

    n_pos = int(y_all.sum())
    n_neg = len(y_all) - n_pos
    pos_weight = max(n_neg / max(n_pos, 1), 1.0)
    print(f"labels: pos={n_pos} neg={n_neg} pos_weight={pos_weight:.2f}")

    skf = StratifiedKFold(n_splits=args.folds, shuffle=True, random_state=42)
    fold_results: list[dict] = []
    best_auc = -1.0
    best_state = None

    for fold_idx, (tr_idx, va_idx) in enumerate(skf.split(x_all, y_all)):
        print(f"\n--- fold {fold_idx + 1}/{args.folds} ---")
        model, fm = train_fold(
            x_all[tr_idx],
            y_all[tr_idx],
            x_all[va_idx],
            y_all[va_idx],
            device=device,
            epochs=args.epochs,
            lr=args.lr,
            pos_weight=pos_weight,
        )
        fm.fold = fold_idx + 1
        print(f"AUC={fm.auc:.4f} sens={fm.sensitivity:.4f} spec={fm.specificity:.4f} n_val={fm.n_val}")
        fold_results.append({
            "fold": fm.fold,
            "auc": round(fm.auc, 4),
            "sensitivity": round(fm.sensitivity, 4),
            "specificity": round(fm.specificity, 4),
            "n_val": fm.n_val,
        })
        if fm.auc > best_auc:
            best_auc = fm.auc
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

    avg_auc = float(np.mean([r["auc"] for r in fold_results]))
    avg_sens = float(np.mean([r["sensitivity"] for r in fold_results]))
    avg_spec = float(np.mean([r["specificity"] for r in fold_results]))

    out_dir = args.output if args.output.is_absolute() else ROOT / args.output
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "backbone": str(backbone),
        "n_pairs": len(pairs),
        "n_folds": args.folds,
        "pos_weight": round(pos_weight, 4),
        "folds": fold_results,
        "mean_auc": round(avg_auc, 4),
        "mean_sensitivity": round(avg_sens, 4),
        "mean_specificity": round(avg_spec, 4),
        "input_dim": INPUT_DIM,
        "feat_dim": FEAT_DIM,
    }

    if best_state:
        torch.save(
            {
                "model_state": best_state,
                "input_dim": INPUT_DIM,
                "backbone": str(backbone),
                "summary": summary,
            },
            out_dir / "best.pt",
        )
    (out_dir / "cv_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"\n=== CV mean AUC={avg_auc:.4f} sens={avg_sens:.4f} spec={avg_spec:.4f} ===")
    print(f"OK {out_dir / 'best.pt'}")


if __name__ == "__main__":
    main()
