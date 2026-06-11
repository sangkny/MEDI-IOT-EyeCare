#!/usr/bin/env python3
"""
파일명: eval_messidor.py
목적: eval_messidor.py 실행 스크립트
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가

DR 모델 평가 — QWK, AUC, Sensitivity, Confusion Matrix.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np


def _load_model_predict(manifest_path: Path, model_path: Path, split: str):
    from services.inference_router import CnnRetinalBackend, InferenceConfig
    from services.retinal_cnn import load_manifest_entries

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data_dir = Path(data["data_dir"])
    if not data_dir.is_dir():
        if data_dir.is_absolute() and str(data_dir).startswith("/workspace/"):
            alt = ROOT / str(data_dir).replace("/workspace/", "", 1)
            if alt.is_dir():
                data_dir = alt
        elif not data_dir.is_absolute():
            alt = ROOT / data_dir
            if alt.is_dir():
                data_dir = alt
    entries = load_manifest_entries(manifest_path, split=split)
    if not entries:
        raise SystemExit(f"split {split!r} empty")

    cfg = InferenceConfig(
        backend="cnn",
        cnn_model_path=model_path if model_path.is_absolute() else ROOT / model_path,
        cnn_confidence_min=0.7,
        cnn_arch="efficientnet_b4",
        cnn_device="cpu",
    )
    backend = CnnRetinalBackend(cfg)

    y_true, y_pred, probs_list = [], [], []
    for e in entries:
        path = data_dir / e["path"]
        grade = int(e["dr_grade"])
        pred = backend._predict_sync(path.read_bytes())
        y_true.append(grade)
        y_pred.append(pred.dr_grade)
        probs_list.append(list(pred.probabilities))
    return y_true, y_pred, np.array(probs_list, dtype=np.float64)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--split", default="test")
    p.add_argument("--output", type=Path, default=ROOT / "reports")
    p.add_argument("--smoke", action="store_true")
    args = p.parse_args()

    manifest = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
    model = args.model if args.model.is_absolute() else ROOT / args.model
    out_dir = args.output if args.output.is_absolute() else ROOT / args.output
    out_dir.mkdir(parents=True, exist_ok=True)

    y_true, y_pred, probs = _load_model_predict(manifest, model, args.split)

    from sklearn.metrics import (
        accuracy_score,
        classification_report,
        cohen_kappa_score,
        confusion_matrix,
        roc_auc_score,
    )

    qwk = float(cohen_kappa_score(y_true, y_pred, weights="quadratic"))
    acc = float(accuracy_score(y_true, y_pred))
    try:
        auc = float(
            roc_auc_score(
                y_true, probs, multi_class="ovr", average="macro", labels=list(range(5))
            )
        )
    except Exception:
        auc = 0.0

    cm = confusion_matrix(y_true, y_pred, labels=list(range(5))).tolist()
    report = classification_report(y_true, y_pred, labels=list(range(5)), output_dict=True)

    referral_true = [1 if g >= 2 else 0 for g in y_true]
    referral_pred = [1 if g >= 2 else 0 for g in y_pred]
    tp = sum(1 for t, p in zip(referral_true, referral_pred) if t == 1 and p == 1)
    fn = sum(1 for t, p in zip(referral_true, referral_pred) if t == 1 and p == 0)
    sensitivity_referral = tp / max(tp + fn, 1)

    per_class = {}
    for g in range(5):
        mask_t = [i for i, v in enumerate(y_true) if v == g]
        if not mask_t:
            per_class[str(g)] = {"support": 0, "recall": 0.0}
            continue
        hits = sum(1 for i in mask_t if y_pred[i] == g)
        per_class[str(g)] = {
            "support": len(mask_t),
            "recall": hits / len(mask_t),
        }

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    result = {
        "model": str(model),
        "manifest": str(manifest),
        "split": args.split,
        "n": len(y_true),
        "qwk": round(qwk, 4),
        "accuracy": round(acc, 4),
        "auc_macro_ovr": round(auc, 4),
        "sensitivity_referral_gte2": round(sensitivity_referral, 4),
        "confusion_matrix": cm,
        "per_class": per_class,
        "classification_report": report,
    }

    out_json = out_dir / f"eval_{args.split}_{stamp}.json"
    out_json.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    try:
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(6, 5))
        im = ax.imshow(cm, cmap="Blues")
        ax.set_xticks(range(5))
        ax.set_yticks(range(5))
        ax.set_xlabel("Predicted")
        ax.set_ylabel("True")
        ax.set_title(f"QWK={qwk:.3f} Acc={acc:.3f}")
        plt.colorbar(im, ax=ax)
        png = out_dir / f"eval_{args.split}_{stamp}.png"
        fig.savefig(png, dpi=120, bbox_inches="tight")
        plt.close(fig)
        print(f"OK plot {png}")
    except Exception as exc:
        print(f"plot_skip: {exc}")

    print(f"OK {out_json}")


if __name__ == "__main__":
    main()
