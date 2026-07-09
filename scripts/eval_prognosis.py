#!/usr/bin/env python3
"""
파일명: scripts/eval_prognosis.py
목적:   학습된 Phase 1 예후 모델 평가 + 환자별 progression 확률

IRB: 국내 임상기관 IRB 승인 (2019) — 로컬 전용
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))

import train_prognosis_mlp as tpm  # noqa: E402

DEFAULT_PAIRS = Path("/dataset/korean_glaucoma_fundus/prognosis_pairs.csv")
DEFAULT_MODEL = ROOT / "models/prognosis_v1/best.pt"
DEFAULT_BACKBONE = ROOT / "models/retinal_v14/best.pt"
DEFAULT_OUT = Path("/dataset/korean_glaucoma_fundus/prognosis_results.json")


def risk_level(prob: float) -> str:
    if prob < 0.3:
        return "low"
    if prob <= 0.6:
        return "medium"
    return "high"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--pairs-csv", type=Path, default=DEFAULT_PAIRS)
    p.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    p.add_argument("--backbone", type=Path, default=DEFAULT_BACKBONE)
    p.add_argument("--output-json", type=Path, default=DEFAULT_OUT)
    p.add_argument("--device", default="cuda")
    args = p.parse_args()

    pairs_path = args.pairs_csv if args.pairs_csv.is_absolute() else Path(args.pairs_csv)
    model_path = args.model if args.model.is_absolute() else ROOT / args.model
    backbone_path = args.backbone if args.backbone.is_absolute() else ROOT / args.backbone

    if not pairs_path.is_file():
        print(f"error: missing {pairs_path}", file=sys.stderr)
        sys.exit(1)
    if not model_path.is_file():
        print(f"error: missing {model_path}", file=sys.stderr)
        sys.exit(1)

    pairs = list(csv.DictReader(open(pairs_path, encoding="utf-8")))
    use_cuda = args.device == "cuda" and torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")

    extractor = tpm.EmbeddingExtractor(backbone_path, device=device)
    x_all, y_all = tpm.build_feature_matrix(pairs, extractor)

    ckpt = torch.load(model_path, map_location="cpu", weights_only=True)
    model = tpm.PrognosisMLP(input_dim=int(ckpt.get("input_dim", tpm.INPUT_DIM)))
    model.load_state_dict(ckpt["model_state"])
    model.eval().to(device)

    with torch.no_grad():
        logits = model(torch.from_numpy(x_all).to(device))
        probs = torch.sigmoid(logits).cpu().numpy()

    auc, sens, spec = tpm._metrics(y_all, probs)

    predictions = []
    for row, prob, label in zip(pairs, probs.tolist(), y_all.tolist()):
        predictions.append({
            "folder_no": row["folder_no"],
            "visit_i": row["visit_i"],
            "visit_j": row["visit_j"],
            "grade_i": int(row["grade_i"]),
            "grade_j": int(row["grade_j"]),
            "days_interval": int(row["days_interval"]),
            "label": int(label),
            "progression_prob": round(float(prob), 4),
            "risk_level": risk_level(float(prob)),
        })

    result = {
        "model": str(model_path),
        "backbone": str(backbone_path),
        "n_pairs": len(pairs),
        "auc": round(auc, 4),
        "sensitivity": round(sens, 4),
        "specificity": round(spec, 4),
        "predictions": predictions,
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"AUC={auc:.4f} sens={sens:.4f} spec={spec:.4f}")
    print(f"OK {args.output_json}")


if __name__ == "__main__":
    main()
