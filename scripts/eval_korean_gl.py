#!/usr/bin/env python3
"""
파일명: scripts/eval_korean_gl.py
목적:   v10c 모델로 한국인 녹내장 안저사진 추론 → 성능 평가
        기존 서양 데이터 훈련 모델의 한국인 NTG 성능 실측

IRB: 국내 임상기관 IRB 승인 (2019) — 로컬 전용
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

IRB_INFO = {
    "institution": "Korean Clinical Institution",
    "approved_year": 2019,
    "storage_policy": "LOCAL_ONLY",
    "external_transfer": "PROHIBITED",
    "git_commit": "PROHIBITED",
}

DEFAULT_OUTPUT_ROOT = Path("/dataset/korean_glaucoma_fundus")
DEFAULT_MODEL = Path("/workspace/models/retinal_v10.onnx")
IMAGE_SIZE = 224


def _sigmoid(x: float) -> float:
    return float(1.0 / (1.0 + np.exp(-x)))


def load_session(model_path: Path):
    import onnxruntime as ort

    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    try:
        session = ort.InferenceSession(str(model_path), providers=providers)
        provider_used = session.get_providers()[0]
    except Exception:
        session = ort.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
        )
        provider_used = "CPUExecutionProvider"
    print(f"ONNX provider: {provider_used}")
    return session


def preprocess_image(path: Path) -> np.ndarray:
    img = cv2.imread(str(path))
    if img is None:
        raise ValueError(f"cannot read {path}")
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(rgb, (IMAGE_SIZE, IMAGE_SIZE), interpolation=cv2.INTER_LANCZOS4)
    arr = resized.astype(np.float32) / 255.0
    return np.transpose(arr, (2, 0, 1))[np.newaxis, ...]


def infer_glaucoma_prob(session, tensor: np.ndarray) -> float:
    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: tensor})
    output_names = [o.name for o in session.get_outputs()]

    for name, out in zip(output_names, outputs):
        if "glaucoma" in name.lower():
            val = float(np.asarray(out).reshape(-1)[0])
            return _sigmoid(val)

    if len(outputs) >= 2:
        val = float(np.asarray(outputs[1]).reshape(-1)[0])
        return _sigmoid(val)

    val = float(np.asarray(outputs[0]).reshape(-1)[0])
    return _sigmoid(val)


def compute_auc(y_true: list[int], y_score: list[float]) -> float | None:
    if len(set(y_true)) < 2:
        return None
    try:
        from sklearn.metrics import roc_auc_score

        return float(roc_auc_score(y_true, y_score))
    except Exception:
        return None


def subgroup_key(row: dict) -> str:
    if int(row.get("is_ntg", 0)):
        return "NTG"
    if int(row.get("is_poag", 0)):
        return "POAG"
    if int(row.get("is_pacg", 0)):
        return "PACG"
    return "OTHER"


def evaluate(
    output_root: Path,
    model_path: Path,
    out_json: Path,
) -> dict:
    labels_path = output_root / "labels_modified.csv"
    if not labels_path.exists():
        print(f"error: missing {labels_path}", file=sys.stderr)
        sys.exit(1)
    if not model_path.exists():
        print(f"error: missing model {model_path}", file=sys.stderr)
        sys.exit(1)

    with open(labels_path, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("modality") == "color"]

    session = load_session(model_path)
    records: list[dict] = []
    y_true: list[int] = []
    y_score: list[float] = []
    by_subgroup: dict[str, list[float]] = defaultdict(list)
    by_grade: dict[int, list[float]] = defaultdict(list)

    for row in rows:
        eye = row["eye"]
        subdir = "OD" if eye == "R" else "OS"
        img_path = output_root / "modified" / "color" / subdir / row["filename"]
        if not img_path.exists():
            continue

        tensor = preprocess_image(img_path)
        prob = infer_glaucoma_prob(session, tensor)
        grade = int(row.get("grade", 0))
        label = 1 if grade > 0 else 0

        records.append({
            "filename": row["filename"],
            "eye": eye,
            "grade": grade,
            "diagnosis": row.get("diagnosis", ""),
            "gl_prob": prob,
            "subgroup": subgroup_key(row),
        })
        y_true.append(label)
        y_score.append(prob)
        by_subgroup[subgroup_key(row)].append(prob)
        by_grade[grade].append(prob)

    severity_y: list[int] = []
    severity_s: list[float] = []
    for r in records:
        if r["grade"] in (1, 3):
            severity_y.append(1 if r["grade"] >= 2 else 0)
            severity_s.append(r["gl_prob"])

    result = {
        "irb": IRB_INFO,
        "evaluated_at": datetime.now().isoformat(),
        "model": str(model_path),
        "n_images": len(records),
        "mean_gl_prob": float(np.mean(y_score)) if y_score else 0.0,
        "detection_rate_0.5": float(np.mean([p >= 0.5 for p in y_score])) if y_score else 0.0,
        "auc_glaucoma_positive": compute_auc(y_true, y_score),
        "auc_severity_grade2plus": compute_auc(severity_y, severity_s),
        "note": (
            "All modified samples are clinical glaucoma (grade>0). "
            "Binary AUC may be undefined; severity AUC uses grade>=2 vs grade==1."
        ),
        "subgroup_mean_prob": {
            k: float(np.mean(v)) for k, v in sorted(by_subgroup.items())
        },
        "subgroup_n": {k: len(v) for k, v in sorted(by_subgroup.items())},
        "grade_mean_prob": {
            str(g): float(np.mean(v)) for g, v in sorted(by_grade.items())
        },
        "samples": records[:50],
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Saved: {out_json}")
    print(f"N={result['n_images']} mean_prob={result['mean_gl_prob']:.4f}")
    print(f"detection@0.5={result['detection_rate_0.5']:.4f}")
    if result["auc_glaucoma_positive"] is not None:
        print(f"AUC(positive)={result['auc_glaucoma_positive']:.4f}")
    if result["auc_severity_grade2plus"] is not None:
        print(f"AUC(severity)={result['auc_severity_grade2plus']:.4f}")
    for sg, prob in result["subgroup_mean_prob"].items():
        print(f"  {sg}: mean={prob:.4f} n={result['subgroup_n'][sg]}")

    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    p.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    p.add_argument(
        "--out-json",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT / "eval_v10c_korean.json",
    )
    args = p.parse_args()
    evaluate(args.output_root, args.model, args.out_json)


if __name__ == "__main__":
    main()
