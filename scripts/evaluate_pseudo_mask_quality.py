#!/usr/bin/env python3
"""
파일명: scripts/evaluate_pseudo_mask_quality.py
목적: G1020 정답 마스크 vs SAM pseudo-mask Dice 품질 평가
히스토리:
  2026-06-19 - 최초 작성 (v13)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.sam_disc_cup_utils import mean_disc_cup_dice


def evaluate(
    *,
    gt_dir: Path,
    pred_dir: Path,
    limit: int = 0,
    bad_threshold: float = 0.70,
) -> dict[str, float | int]:
    gt_files = sorted(gt_dir.glob("*_mask.png"))
    if limit > 0:
        gt_files = gt_files[:limit]
    scores: list[float] = []
    missing = 0
    for gt_path in gt_files:
        pred_path = pred_dir / gt_path.name
        if not pred_path.is_file():
            missing += 1
            continue
        gt = cv2.imread(str(gt_path), cv2.IMREAD_GRAYSCALE)
        pred = cv2.imread(str(pred_path), cv2.IMREAD_GRAYSCALE)
        if gt is None or pred is None:
            missing += 1
            continue
        if gt.shape != pred.shape:
            pred = cv2.resize(pred, (gt.shape[1], gt.shape[0]), interpolation=cv2.INTER_NEAREST)
        scores.append(mean_disc_cup_dice(pred, gt))

    if not scores:
        return {"n": 0, "missing": missing}

    arr = np.array(scores, dtype=np.float64)
    bad = int((arr < bad_threshold).sum())
    return {
        "n": len(scores),
        "missing": missing,
        "mean_dice": float(arr.mean()),
        "median_dice": float(np.median(arr)),
        "min_dice": float(arr.min()),
        "p10_dice": float(np.percentile(arr, 10)),
        "bad_count": bad,
        "bad_pct": 100.0 * bad / len(scores),
        "pass_085": int((arr >= 0.85).sum()),
        "pass_085_pct": 100.0 * (arr >= 0.85).sum() / len(scores),
    }


def main() -> None:
    p = argparse.ArgumentParser(description="SAM pseudo-mask quality vs G1020 GT")
    p.add_argument("--dataset-root", type=Path, default=Path("/dataset"))
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--bad-threshold", type=float, default=0.70)
    args = p.parse_args()

    gt_dir = args.dataset_root / "disc_cup_masks/G1020"
    pred_dir = args.dataset_root / "disc_cup_masks/pseudo/G1020"
    stats = evaluate(gt_dir=gt_dir, pred_dir=pred_dir, limit=args.limit, bad_threshold=args.bad_threshold)
    print(f"GT dir:   {gt_dir}")
    print(f"Pred dir: {pred_dir}")
    for k, v in stats.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.4f}")
        else:
            print(f"  {k}: {v}")
    if stats.get("n", 0) and stats.get("mean_dice", 0) >= 0.85:
        print("OK: mean Dice >= 0.85 — training usable")
    elif stats.get("n", 0):
        print("WARN: mean Dice < 0.85 — review before v13 train")


if __name__ == "__main__":
    main()
