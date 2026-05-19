#!/usr/bin/env python3
"""Messidor hold-out 평가 (D R4-ML D4).

지표: Confusion Matrix (5×5), class별 Sensitivity/Specificity,
Quadratic Weighted Kappa (QWK), ROC-AUC (OvR).

사용:

  python scripts/eval_messidor.py \\
    --model models/retinal_v1.onnx \\
    --manifest datasets/messidor2/manifest.json \\
    --split val \\
    --output reports/

  # 합성 스모크 (데이터셋 불필요)
  python scripts/eval_messidor.py --smoke --model models/retinal_v1.onnx
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _quadratic_weighted_kappa(y_true: list[int], y_pred: list[int], n: int = 5) -> float:
    try:
        from sklearn.metrics import cohen_kappa_score

        return float(cohen_kappa_score(y_true, y_pred, weights="quadratic"))
    except Exception:
        return 0.0


def _per_class_sens_spec(cm: list[list[int]], n: int = 5) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for c in range(n):
        tp = cm[c][c]
        fn = sum(cm[c][j] for j in range(n)) - tp
        fp = sum(cm[i][c] for i in range(n)) - tp
        tn = sum(sum(row) for row in cm) - tp - fn - fp
        sens = tp / (tp + fn) if (tp + fn) else 0.0
        spec = tn / (tn + fp) if (tn + fp) else 0.0
        out[str(c)] = {
            "sensitivity": round(sens, 4),
            "specificity": round(spec, 4),
            "support": int(sum(cm[c])),
        }
    return out


def _load_predictor(model_path: Path, arch: str | None, device: str):
    """ONNX 우선, 없으면 torch."""
    if model_path.suffix == ".onnx" and model_path.is_file():
        import onnxruntime as ort

        sess = ort.InferenceSession(
            str(model_path), providers=["CPUExecutionProvider"]
        )
        inp = sess.get_inputs()[0].name

        def predict(tensor):
            import numpy as np

            arr = tensor.numpy() if hasattr(tensor, "numpy") else np.asarray(tensor)
            logits = sess.run(None, {inp: arr})[0]
            return logits

        return predict, "onnx"

    import torch

    from services.retinal_cnn import build_dr_classifier, dr_prediction_from_logits

    pt = model_path if model_path.suffix == ".pt" else model_path.with_suffix(".pt")
    try:
        ckpt = torch.load(pt, map_location="cpu", weights_only=False)
    except TypeError:
        ckpt = torch.load(pt, map_location="cpu")
    arch_key = arch or (ckpt.get("arch") if isinstance(ckpt, dict) else None) or "efficientnet_b4"
    model, _ = build_dr_classifier(arch=str(arch_key), pretrained=False)
    if isinstance(ckpt, dict) and "state_dict" in ckpt:
        model.load_state_dict(ckpt["state_dict"])
    else:
        model.load_state_dict(ckpt)
    dev = torch.device(device)
    model.to(dev)
    model.eval()

    def predict(tensor):
        with torch.no_grad():
            return model(tensor.to(dev)).cpu().numpy()

    return predict, "torch"


def run_eval(args: argparse.Namespace) -> int:
    from services.retinal_cnn import (
        DR_NUM_CLASSES,
        DEFAULT_IMAGE_SIZE,
        dr_prediction_from_logits,
        load_image_tensor_from_path,
        load_manifest_entries,
        resolve_preprocess_mode,
    )

    out_dir = Path(args.output)
    if not out_dir.is_absolute():
        out_dir = _REPO / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    preprocess = resolve_preprocess_mode(args.preprocess)
    image_size = args.image_size
    y_true: list[int] = []
    y_pred: list[int] = []
    y_prob: list[list[float]] = []

    model_path = Path(args.model)
    if not model_path.is_absolute():
        model_path = _REPO / model_path

    if args.smoke:
        import torch

        from services.retinal_cnn import build_dr_classifier

        model, _ = build_dr_classifier(arch=args.arch or "efficientnet_b4", pretrained=False)
        model.eval()
        for grade in range(DR_NUM_CLASSES):
            x = torch.randn(1, 3, image_size, image_size)
            logits = model(x)
            pred = dr_prediction_from_logits(logits[0])
            y_true.append(grade)
            y_pred.append(pred.dr_grade)
            y_prob.append(list(pred.probabilities))
    else:
        manifest = Path(args.manifest)
        if not manifest.is_absolute():
            manifest = _REPO / manifest
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data_dir = Path(data.get("data_dir", "."))
        if not data_dir.is_absolute():
            data_dir = manifest.parent / data_dir

        entries = load_manifest_entries(manifest, args.split)
        if not entries:
            print(f"[eval_messidor] no entries for split={args.split!r}", file=sys.stderr)
            return 2

        if not model_path.is_file():
            print(f"[eval_messidor] model not found: {model_path}", file=sys.stderr)
            return 2

        predict_fn, backend = _load_predictor(model_path, args.arch, args.device)
        meta_path = model_path.with_name(model_path.stem + ".meta.json")
        if meta_path.is_file():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            image_size = int(meta.get("image_size") or image_size)
            preprocess = resolve_preprocess_mode(
                meta.get("preprocess") or preprocess
            )

        for e in entries:
            rel = e.get("path") or e.get("filename")
            if not rel:
                continue
            img_path = data_dir / rel
            if not img_path.is_file():
                continue
            tensor = load_image_tensor_from_path(
                img_path,
                image_size=image_size,
                preprocess_mode=preprocess,
            )
            logits = predict_fn(tensor)
            if hasattr(logits, "shape") and len(logits.shape) == 2:
                logits = logits[0]
            pred = dr_prediction_from_logits(logits)
            y_true.append(int(e["dr_grade"]))
            y_pred.append(pred.dr_grade)
            y_prob.append(list(pred.probabilities))

        print(f"[eval_messidor] evaluated {len(y_true)} images via {backend}")

    if not y_true:
        print("[eval_messidor] no samples", file=sys.stderr)
        return 2

    from sklearn.metrics import (
        accuracy_score,
        confusion_matrix,
        roc_auc_score,
    )

    cm = confusion_matrix(y_true, y_pred, labels=list(range(DR_NUM_CLASSES)))
    cm_list = cm.tolist()
    acc = float(accuracy_score(y_true, y_pred))
    qwk = _quadratic_weighted_kappa(y_true, y_pred, DR_NUM_CLASSES)
    per_class = _per_class_sens_spec(cm_list, DR_NUM_CLASSES)

    try:
        auc = float(
            roc_auc_score(
                y_true,
                y_prob,
                multi_class="ovr",
                average="weighted",
                labels=list(range(DR_NUM_CLASSES)),
            )
        )
    except Exception:
        auc = None

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": str(model_path),
        "split": args.split,
        "preprocess": preprocess,
        "n_samples": len(y_true),
        "accuracy": round(acc, 4),
        "quadratic_weighted_kappa": round(qwk, 4),
        "roc_auc_ovr_weighted": round(auc, 4) if auc is not None else None,
        "confusion_matrix": cm_list,
        "per_class": per_class,
        "clinical_note": "referral-grade sensitivity target >= 0.85 for moderate+ DR",
    }

    json_path = out_dir / f"eval_messidor_{stamp}.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    try:
        import matplotlib.pyplot as plt
        import numpy as np

        fig, ax = plt.subplots(figsize=(6, 5))
        im = ax.imshow(np.array(cm_list))
        ax.set_xticks(range(DR_NUM_CLASSES))
        ax.set_yticks(range(DR_NUM_CLASSES))
        ax.set_xlabel("Predicted DR grade")
        ax.set_ylabel("True DR grade")
        ax.set_title(f"Messidor eval acc={acc:.3f} QWK={qwk:.3f}")
        for i in range(DR_NUM_CLASSES):
            for j in range(DR_NUM_CLASSES):
                ax.text(j, i, cm_list[i][j], ha="center", va="center", color="white")
        fig.colorbar(im, ax=ax)
        png_path = out_dir / f"eval_messidor_{stamp}.png"
        fig.tight_layout()
        fig.savefig(png_path, dpi=120)
        plt.close(fig)
        print(f"[eval_messidor] wrote {png_path}")
    except Exception as exc:
        print(f"[eval_messidor] plot skipped: {exc}")

    print(
        f"[eval_messidor] n={len(y_true)} acc={acc:.4f} QWK={qwk:.4f} "
        f"AUC={auc} -> {json_path}"
    )
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Messidor hold-out DR CNN eval")
    p.add_argument("--model", default="models/retinal_v1.onnx")
    p.add_argument("--manifest", default="datasets/messidor2/manifest.json")
    p.add_argument("--split", default="val", choices=["train", "val", "test"])
    p.add_argument("--output", default="reports")
    p.add_argument("--arch", default=None)
    p.add_argument("--preprocess", default=None)
    p.add_argument("--image-size", type=int, default=224)
    p.add_argument("--device", default="cpu")
    p.add_argument("--smoke", action="store_true")
    args = p.parse_args()
    try:
        return run_eval(args)
    except ImportError as e:
        print(f"[eval_messidor] missing dependency: {e}", file=sys.stderr)
        print("  pip install -r requirements-ml.txt", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
