#!/usr/bin/env python3
"""
파일명: scripts/analyze_gl_trend.py
목적: 복수방문 환자의 방문별 GL 확률 변화 추이 분석
      (Grade 변화 대신 AI 확률 변화로 조기 신호 탐색)

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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.retinal_cnn import preprocess_fundus_array

IRB_INFO = {
    "institution": "Korean Clinical Institution",
    "approved_year": 2019,
    "storage_policy": "LOCAL_ONLY",
}

DEFAULT_TS = Path("/dataset/korean_glaucoma_fundus/timeseries_labels.csv")
DEFAULT_ROOT = Path("/dataset/korean_glaucoma_fundus")
DEFAULT_MODEL = ROOT / "models/retinal_v15.onnx"
DEFAULT_OUT = ROOT / "gl_trend_analysis.json"
IMAGE_SIZE = 224
DELTA_THRESHOLD = 0.1


def _sigmoid(x: float) -> float:
    return float(1.0 / (1.0 + np.exp(-x)))


def _fundus_path(data_root: Path, fname: str, eye: str) -> Path | None:
    if not fname or not fname.strip():
        return None
    sub = "OD" if eye == "R" else "OS"
    return data_root / "origin" / "fundus" / sub / fname.strip()


def load_session(model_path: Path):
    import onnxruntime as ort

    try:
        session = ort.InferenceSession(
            str(model_path),
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
        )
    except Exception:
        session = ort.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
        )
    print(f"ONNX provider: {session.get_providers()[0]}")
    return session


def preprocess_for_onnx(path: Path) -> np.ndarray:
    img = cv2.imread(str(path))
    if img is None:
        raise ValueError(f"cannot read {path}")
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    arr = preprocess_fundus_array(rgb, mode="clahe")
    resized = cv2.resize(arr, (IMAGE_SIZE, IMAGE_SIZE), interpolation=cv2.INTER_LANCZOS4)
    t = resized.astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    t = (t - mean) / std
    return np.transpose(t, (2, 0, 1))[np.newaxis, ...]


def infer_glaucoma_prob(session, tensor: np.ndarray) -> float:
    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: tensor})
    output_names = [o.name for o in session.get_outputs()]

    for name, out in zip(output_names, outputs):
        if "glaucoma" in name.lower() and "grade" not in name.lower():
            val = float(np.asarray(out).reshape(-1)[0])
            return _sigmoid(val)

    if len(outputs) >= 2:
        val = float(np.asarray(outputs[1]).reshape(-1)[0])
        return _sigmoid(val)

    val = float(np.asarray(outputs[0]).reshape(-1)[0])
    return _sigmoid(val)


def visit_gl_prob(
    session,
    data_root: Path,
    row: dict,
) -> float | None:
    probs: list[float] = []
    for eye, key in (("R", "file_fundus_R"), ("L", "file_fundus_L")):
        fname = (row.get(key) or "").strip()
        if not fname:
            continue
        p = _fundus_path(data_root, fname, eye)
        if p is None or not p.is_file():
            continue
        try:
            tensor = preprocess_for_onnx(p)
            probs.append(infer_glaucoma_prob(session, tensor))
        except ValueError:
            continue
    if not probs:
        return None
    return float(sum(probs) / len(probs))


def analyze(
    ts_csv: Path,
    data_root: Path,
    model_path: Path,
    *,
    delta_threshold: float = DELTA_THRESHOLD,
) -> dict:
    rows = list(csv.DictReader(open(ts_csv, encoding="utf-8")))
    by_patient: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_patient[row["folder_no"]].append(row)

    multi = {pid: v for pid, v in by_patient.items() if len(v) >= 2}
    session = load_session(model_path)

    patient_series: list[dict] = []
    pair_records: list[dict] = []

    for folder_no, visits in sorted(multi.items(), key=lambda x: int(x[0])):
        sorted_v = sorted(visits, key=lambda x: int(x.get("visit_idx") or 0))
        visit_probs: list[dict] = []
        for v in sorted_v:
            prob = visit_gl_prob(session, data_root, v)
            if prob is None:
                continue
            visit_probs.append({
                "visit_idx": int(v.get("visit_idx") or 0),
                "date": v.get("date", ""),
                "grade": int(v.get("grade") or 0),
                "gl_prob": round(prob, 4),
            })

        if len(visit_probs) < 2:
            continue

        max_delta = 0.0
        for i in range(len(visit_probs) - 1):
            cur, nxt = visit_probs[i], visit_probs[i + 1]
            delta = nxt["gl_prob"] - cur["gl_prob"]
            max_delta = max(max_delta, delta)
            vi = sorted_v[i]
            grade_change = vi.get("grade_change", "stable")
            pair_records.append({
                "folder_no": folder_no,
                "visit_i": cur["visit_idx"],
                "visit_j": nxt["visit_idx"],
                "gl_prob_i": cur["gl_prob"],
                "gl_prob_j": nxt["gl_prob"],
                "delta_prob": round(delta, 4),
                "grade_change": grade_change,
                "grade_i": cur["grade"],
                "grade_j": nxt["grade"],
            })

        patient_series.append({
            "folder_no": folder_no,
            "n_visits_scored": len(visit_probs),
            "visits": visit_probs,
            "max_delta_prob": round(max_delta, 4),
            "rising_ge_threshold": max_delta >= delta_threshold,
        })

    rising_patients = [p for p in patient_series if p["rising_ge_threshold"]]
    progression_pairs = [r for r in pair_records if r["grade_change"] == "progression"]
    rising_on_progression = sum(
        1 for r in pair_records
        if r["grade_change"] == "progression" and r["delta_prob"] >= delta_threshold
    )

    deltas = [r["delta_prob"] for r in pair_records]
    prog_deltas = [r["delta_prob"] for r in pair_records if r["grade_change"] == "progression"]
    stable_deltas = [r["delta_prob"] for r in pair_records if r["grade_change"] == "stable"]

    summary = {
        "irb": IRB_INFO,
        "analyzed_at": datetime.now().isoformat(timespec="seconds"),
        "model": str(model_path),
        "delta_threshold": delta_threshold,
        "multi_visit_patients": len(multi),
        "patients_with_scored_visits": len(patient_series),
        "adjacent_pairs_scored": len(pair_records),
        "patients_gl_rise_ge_threshold": len(rising_patients),
        "patients_gl_rise_ge_threshold_pct": round(
            len(rising_patients) / max(len(patient_series), 1) * 100, 1
        ),
        "grade_progression_pairs": len(progression_pairs),
        "progression_pairs_with_gl_rise_ge_threshold": rising_on_progression,
        "delta_prob_stats": {
            "all_mean": round(float(np.mean(deltas)), 4) if deltas else None,
            "progression_mean": round(float(np.mean(prog_deltas)), 4) if prog_deltas else None,
            "stable_mean": round(float(np.mean(stable_deltas)), 4) if stable_deltas else None,
        },
        "headline": (
            f"GL 확률 {delta_threshold} 이상 상승 환자: "
            f"{len(rising_patients)}/{len(patient_series)} "
            f"({len(rising_patients) / max(len(patient_series), 1) * 100:.1f}%)"
        ),
        "patients": patient_series,
        "pairs": pair_records,
    }
    return summary


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--timeseries-csv", type=Path, default=DEFAULT_TS)
    p.add_argument("--data-root", type=Path, default=DEFAULT_ROOT)
    p.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    p.add_argument("--output-json", type=Path, default=DEFAULT_OUT)
    p.add_argument("--delta-threshold", type=float, default=DELTA_THRESHOLD)
    args = p.parse_args()

    ts_path = args.timeseries_csv
    model_path = args.model if args.model.is_absolute() else ROOT / args.model

    if not ts_path.is_file():
        print(f"error: missing {ts_path}", file=sys.stderr)
        sys.exit(1)
    if not model_path.is_file():
        print(f"error: missing ONNX model {model_path}", file=sys.stderr)
        print("  → python3 scripts/export_v15_onnx.py --checkpoint models/retinal_v15/best.pt ...")
        sys.exit(1)

    summary = analyze(
        ts_path,
        args.data_root,
        model_path,
        delta_threshold=args.delta_threshold,
    )

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(summary["headline"])
    print(f"OK {args.output_json}")


if __name__ == "__main__":
    main()
