#!/usr/bin/env python3
"""Messidor-2 train/val manifest 생성 (D R4-ML D1).

``annotations/messidor_data.csv`` 를 읽어 stratified split 후 JSON manifest 를 쓴다.
실제 이미지 byte 는 필요 없음 — CNN 학습 Job·eval 스크립트의 SSOT.

사용:

  python scripts/build_messidor2_manifest.py \\
    --data-dir /data/messidor2 \\
    --output datasets/messidor2/manifest.json

  # Docker
  docker compose exec medi-iot-api \\
    python scripts/build_messidor2_manifest.py --data-dir /data/messidor2
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from import_messidor2 import DR_TO_ICD10, DR_TO_SEVERITY, _parse_annotations


def _stratified_split(
    rows: list[dict],
    *,
    val_ratio: float,
    seed: int,
) -> tuple[list[dict], list[dict]]:
    """``dr_grade`` 별로 train/val 분할 (각 grade 최소 1장은 train)."""
    by_grade: dict[int, list[dict]] = defaultdict(list)
    for r in rows:
        by_grade[int(r["dr_grade"])].append(r)

    train: list[dict] = []
    val: list[dict] = []
    rng = random.Random(seed)

    for grade, items in sorted(by_grade.items()):
        shuffled = items[:]
        rng.shuffle(shuffled)
        n_val = max(0, int(round(len(shuffled) * val_ratio)))
        if len(shuffled) > 1 and n_val >= len(shuffled):
            n_val = len(shuffled) - 1
        val.extend(shuffled[:n_val])
        train.extend(shuffled[n_val:])

    rng.shuffle(train)
    rng.shuffle(val)
    return train, val


def _enrich_entry(ann: dict, *, data_dir: Path) -> dict:
    icd = DR_TO_ICD10.get(int(ann["dr_grade"]))
    sev = DR_TO_SEVERITY.get(int(ann["dr_grade"]), "none")
    rel = Path("images") / ann["image_id"]
    return {
        "image_id": ann["image_id"],
        "dr_grade": int(ann["dr_grade"]),
        "me_grade": int(ann["me_grade"]),
        "laterality": ann["laterality"],
        "icd10": icd,
        "severity": sev,
        "path": str(rel).replace("\\", "/"),
        "exists": (data_dir / rel).is_file(),
    }


def build_manifest(
    data_dir: Path,
    *,
    val_ratio: float = 0.2,
    seed: int = 42,
    limit: int = 0,
) -> dict:
    ann_csv = data_dir / "annotations" / "messidor_data.csv"
    if not ann_csv.exists():
        raise FileNotFoundError(f"annotations not found: {ann_csv}")

    rows = _parse_annotations(ann_csv)
    if limit > 0:
        rows = rows[:limit]
    if not rows:
        raise ValueError("no annotation rows")

    train_raw, val_raw = _stratified_split(rows, val_ratio=val_ratio, seed=seed)
    train = [_enrich_entry(r, data_dir=data_dir) for r in train_raw]
    val = [_enrich_entry(r, data_dir=data_dir) for r in val_raw]

    grade_counts = Counter(int(r["dr_grade"]) for r in rows)
    return {
        "version": 1,
        "source": "messidor-2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data_dir": str(data_dir.resolve()),
        "split": {
            "method": "stratified_by_dr_grade",
            "val_ratio": val_ratio,
            "seed": seed,
        },
        "train": train,
        "val": val,
        "stats": {
            "total": len(rows),
            "train": len(train),
            "val": len(val),
            "by_dr_grade": dict(sorted(grade_counts.items())),
            "train_by_dr_grade": dict(
                sorted(Counter(e["dr_grade"] for e in train).items())
            ),
            "val_by_dr_grade": dict(
                sorted(Counter(e["dr_grade"] for e in val).items())
            ),
            "missing_files": sum(
                1 for e in train + val if not e["exists"]
            ),
        },
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Messidor-2 train/val manifest (D R4-ML D1)")
    p.add_argument("--data-dir", default="/data/messidor2")
    p.add_argument(
        "--output",
        default="datasets/messidor2/manifest.json",
        help="manifest JSON path (repo-relative or absolute)",
    )
    p.add_argument("--val-ratio", type=float, default=0.2)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--limit", type=int, default=0)
    args = p.parse_args()

    data_dir = Path(args.data_dir).expanduser().resolve()
    try:
        manifest = build_manifest(
            data_dir,
            val_ratio=args.val_ratio,
            seed=args.seed,
            limit=args.limit,
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"[manifest] error: {e}", file=sys.stderr)
        return 2

    out = Path(args.output).expanduser()
    if not out.is_absolute():
        out = Path(__file__).resolve().parent.parent / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    st = manifest["stats"]
    print(
        f"[manifest] wrote {out} — total={st['total']} "
        f"train={st['train']} val={st['val']} missing_files={st['missing_files']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
