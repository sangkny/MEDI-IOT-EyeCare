#!/usr/bin/env python3
"""
검증셋 GL AUC — v10c 단독 vs v10c+glaucoma_v2 앙상블 비교.

예:
  python scripts/measure_gl_auc.py \\
    --manifest training/manifests/unified_v10.json \\
    --max-samples 500
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _manifest_splits(data: dict) -> tuple[list, list]:
    splits = data.get("splits") or {}
    return list(splits.get("train") or []), list(splits.get("val") or [])


def _resolve_image_path(entry: dict, data_dir: Path, dr_data_dir: Path | None) -> Path:
    rel = str(entry["path"]).replace("\\", "/")
    if rel.startswith("/"):
        return Path(rel)
    if dr_data_dir and (
        rel.startswith("resized_cache/")
        or "/resized_cache/" in rel
        or rel.startswith("data/")
    ):
        return dr_data_dir / rel.lstrip("/")
    return data_dir / rel


async def _evaluate(args: argparse.Namespace) -> dict[str, float]:
    from sklearn.metrics import roc_auc_score

    from services.gl_ensemble import GlaucomaEnsemble
    from services.glaucoma_cnn import get_glaucoma_backend
    from services.v10_cnn import get_v10_backend

    manifest_path = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    _, val_entries = _manifest_splits(data)
    data_dir = Path(str(data.get("data_dir") or "/dataset"))
    dr_raw = data.get("dr_data_dir")
    dr_data_dir = Path(str(dr_raw)) if dr_raw else None

    gl_entries = [
        e
        for e in val_entries
        if "glaucoma" in (e.get("available_labels") or {})
    ]
    if args.max_samples and len(gl_entries) > args.max_samples:
        gl_entries = gl_entries[: args.max_samples]

    if not gl_entries:
        print("WARN: no GL validation samples")
        return {"v10c_auc": 0.0, "ensemble_auc": 0.0, "n": 0.0}

    v10 = get_v10_backend()
    v2 = get_glaucoma_backend()
    ens = GlaucomaEnsemble()

    ys: list[float] = []
    v10c_scores: list[float] = []
    ensemble_scores: list[float] = []

    for entry in gl_entries:
        path = _resolve_image_path(entry, data_dir, dr_data_dir)
        if not path.is_file():
            continue
        image_bytes = path.read_bytes()
        v10_pred = v10.predict_sync(image_bytes)
        v10c_prob = float(v10_pred.glaucoma.probability)
        out = await ens.predict(
            image_bytes=image_bytes,
            v10c_prob=v10c_prob,
            glaucoma_v2_model=v2,
        )
        label = float(entry["available_labels"]["glaucoma"])
        ys.append(label)
        v10c_scores.append(v10c_prob)
        ensemble_scores.append(float(out["probability"]))

    if len(set(int(y) for y in ys)) < 2:
        print("WARN: single-class validation subset")
        return {"v10c_auc": 0.0, "ensemble_auc": 0.0, "n": float(len(ys))}

    v10c_auc = float(roc_auc_score(ys, v10c_scores))
    ensemble_auc = float(roc_auc_score(ys, ensemble_scores))
    return {"v10c_auc": v10c_auc, "ensemble_auc": ensemble_auc, "n": float(len(ys))}


def main() -> None:
    p = argparse.ArgumentParser(description="GL AUC — v10c vs ensemble")
    p.add_argument("--manifest", type=Path, default=ROOT / "training/manifests/unified_v10.json")
    p.add_argument("--max-samples", type=int, default=0, help="0=전체 검증셋")
    args = p.parse_args()

    metrics = asyncio.run(_evaluate(args))
    print(f"n={int(metrics['n'])}")
    print(f"v10c AUC:      {metrics['v10c_auc']:.4f}")
    print(f"ensemble AUC:  {metrics['ensemble_auc']:.4f}")
    target = 0.900
    if metrics["ensemble_auc"] >= target:
        print(f"OK — ensemble AUC >= {target}")
    else:
        print(f"목표 {target}+ 미달 (현재 {metrics['ensemble_auc']:.4f})")


if __name__ == "__main__":
    main()
