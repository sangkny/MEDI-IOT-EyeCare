#!/usr/bin/env python3
"""안저 DR 데이터셋 통합 Manifest 생성 (SSOT).

지원: APTOS · Messidor-2 · IDRiD · EyePACS · synthetic

예:
  python training/make_manifest.py \\
    --datasets aptos messidor2 idrid \\
    --output training/manifests/unified_v4.json

  python training/make_manifest.py \\
    --datasets aptos messidor2 idrid eyepacs \\
    --output training/manifests/unified_eyepacs.json \\
    --eyepacs-dir /dataset/EyePACS_raw
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MESSIDOR_GRADE_MAP = {0: 0, 1: 1, 2: 2, 3: 4}


def _rel_path(base: Path, file: Path) -> str:
    return file.resolve().relative_to(base.resolve()).as_posix()


def load_aptos(data_root: Path) -> list[dict]:
    csv_path = data_root / "aptos2019_raw" / "train.csv"
    img_dir = data_root / "aptos2019_raw" / "train_images"
    if not csv_path.is_file():
        print(f"  warn APTOS CSV missing: {csv_path}")
        return []
    out: list[dict] = []
    with csv_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            img = img_dir / f"{row['id_code']}.png"
            if img.is_file():
                out.append(
                    {
                        "path": _rel_path(data_root, img),
                        "dr_grade": int(row["diagnosis"]),
                        "source": "aptos",
                    }
                )
    return out


def load_messidor2(data_root: Path) -> list[dict]:
    csv_path = data_root / "Messidor-2_raw" / "messidor_data.csv"
    img_dir = data_root / "Messidor-2_raw" / "IMAGES"
    if not csv_path.is_file():
        print(f"  warn Messidor-2 CSV missing: {csv_path}")
        return []
    out: list[dict] = []
    with csv_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("adjudicated_gradable") != "1":
                continue
            img = img_dir / row["image_id"]
            if img.is_file():
                grade = MESSIDOR_GRADE_MAP.get(int(row["adjudicated_dr_grade"]), 0)
                out.append(
                    {
                        "path": _rel_path(data_root, img),
                        "dr_grade": grade,
                        "source": "messidor2",
                    }
                )
    return out


def load_idrid(data_root: Path) -> list[dict]:
    base = data_root / "IDRiD_raw" / "B. Disease Grading"
    pairs = [
        (
            base / "2. Groundtruths" / "a. IDRiD_Disease Grading_Training Labels.csv",
            base / "1. Original Images" / "a. Training Set",
        ),
        (
            base / "2. Groundtruths" / "b. IDRiD_Disease Grading_Testing Labels.csv",
            base / "1. Original Images" / "b. Testing Set",
        ),
    ]
    out: list[dict] = []
    for csv_path, img_dir in pairs:
        if not csv_path.is_file():
            continue
        with csv_path.open(encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if not row or not row[0].strip():
                    continue
                name = row[0].strip()
                grade = int(row[1].strip())
                img = img_dir / f"{name}.jpg"
                if img.is_file():
                    out.append(
                        {
                            "path": _rel_path(data_root, img),
                            "dr_grade": grade,
                            "source": "idrid",
                        }
                    )
    return out


def load_eyepacs(eyepacs_dir: Path, *, data_root: Path) -> list[dict]:
    csv_path = eyepacs_dir / "trainLabels.csv"
    img_dir = eyepacs_dir / "train"
    if not csv_path.is_file():
        print(f"  warn EyePACS CSV missing: {csv_path}")
        return []
    out: list[dict] = []
    with csv_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            img = img_dir / f"{row['image']}.jpeg"
            if img.is_file():
                try:
                    rel = _rel_path(data_root, img)
                except ValueError:
                    rel = img.as_posix()
                out.append(
                    {
                        "path": rel,
                        "dr_grade": int(row["level"]),
                        "source": "eyepacs",
                    }
                )
    return out


def load_synthetic(data_root: Path) -> list[dict]:
    manifest = data_root / "synthetic_manifest.json"
    if not manifest.is_file():
        alt = ROOT / "data" / "synthetic_manifest.json"
        manifest = alt if alt.is_file() else manifest
    if not manifest.is_file():
        print(f"  warn synthetic manifest missing: {manifest}")
        return []
    raw = json.loads(manifest.read_text(encoding="utf-8"))
    out: list[dict] = []
    if isinstance(raw, dict):
        for split in ("train", "val", "test"):
            for e in raw.get(split) or []:
                out.append(
                    {
                        "path": e["path"],
                        "dr_grade": int(e.get("dr_grade", e.get("label", 0))),
                        "source": "synthetic",
                    }
                )
    elif isinstance(raw, list):
        for e in raw:
            out.append(
                {
                    "path": e["path"],
                    "dr_grade": int(e.get("dr_grade", e.get("label", 0))),
                    "source": "synthetic",
                }
            )
    return out


LOADERS = {
    "aptos": load_aptos,
    "messidor2": load_messidor2,
    "idrid": load_idrid,
    "synthetic": load_synthetic,
}


def _data_dir_key(data_root: Path) -> str:
    try:
        return data_root.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(data_root)


def main() -> None:
    p = argparse.ArgumentParser(description="안저 DR 통합 manifest 생성")
    p.add_argument(
        "--datasets",
        nargs="+",
        default=["aptos", "messidor2", "idrid"],
        choices=["aptos", "messidor2", "idrid", "eyepacs", "synthetic"],
    )
    p.add_argument(
        "--output",
        default="training/manifests/unified.json",
        help="출력 JSON (프로젝트 루트 기준)",
    )
    p.add_argument("--sample", type=int, default=0, help="등급당 최대 장수 (0=전체)")
    p.add_argument(
        "--split",
        nargs=3,
        type=float,
        default=[0.8, 0.1, 0.1],
        metavar=("TRAIN", "VAL", "TEST"),
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--data-root", default="data", help="데이터 루트 (프로젝트 기준)")
    p.add_argument(
        "--eyepacs-dir",
        default=os.environ.get(
            "EYEPACS_DIR",
            "/dataset/EyePACS_raw",
        ),
        help="EyePACS 루트 (컨테이너: /dataset/EyePACS_raw, 호스트는 --eyepacs-dir 지정)",
    )
    args = p.parse_args()

    random.seed(args.seed)
    data_root = (ROOT / args.data_root).resolve()
    eyepacs_dir = Path(args.eyepacs_dir)
    output_path = (ROOT / args.output).resolve() if not Path(args.output).is_absolute() else Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n{'=' * 50}")
    print(f"Manifest: {args.datasets}")
    print(f"data_root: {_data_dir_key(data_root)}")
    print(f"{'=' * 50}")

    all_samples: list[dict] = []
    for ds in args.datasets:
        if ds == "eyepacs":
            items = load_eyepacs(eyepacs_dir, data_root=data_root)
        else:
            items = LOADERS[ds](data_root)
        print(f"  {ds:12s}: {len(items):>6}")
        all_samples.extend(items)

    if not all_samples:
        raise SystemExit("no samples — check paths and CSV files")

    if args.sample > 0:
        by_grade: dict[int, list[dict]] = {g: [] for g in range(5)}
        for s in all_samples:
            by_grade[s["dr_grade"]].append(s)
        all_samples = []
        for items in by_grade.values():
            random.shuffle(items)
            all_samples.extend(items[: args.sample])

    random.shuffle(all_samples)
    total = len(all_samples)
    n_train = int(total * args.split[0])
    n_val = int(total * args.split[1])

    for i, s in enumerate(all_samples):
        s["split"] = "train" if i < n_train else "val" if i < n_train + n_val else "test"

    grade_dist = dict(sorted(Counter(s["dr_grade"] for s in all_samples).items()))
    source_dist = dict(Counter(s["source"] for s in all_samples))
    split_dist = dict(Counter(s["split"] for s in all_samples))

    print(f"\n  total:  {total}")
    print(f"  grade:  {grade_dist}")
    print(f"  source: {source_dist}")
    print(f"  split:  {split_dist}")

    payload = {
        "data_dir": _data_dir_key(data_root),
        "meta": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "datasets": args.datasets,
            "total": total,
            "split": split_dist,
            "grade_dist": {str(k): v for k, v in grade_dist.items()},
            "source_dist": source_dist,
            "seed": args.seed,
        },
        "train": [
            {"path": s["path"], "dr_grade": s["dr_grade"]}
            for s in all_samples
            if s["split"] == "train"
        ],
        "val": [
            {"path": s["path"], "dr_grade": s["dr_grade"]}
            for s in all_samples
            if s["split"] == "val"
        ],
        "test": [
            {"path": s["path"], "dr_grade": s["dr_grade"]}
            for s in all_samples
            if s["split"] == "test"
        ],
    }

    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nOK {output_path.relative_to(ROOT)}")
    print(f"{'=' * 50}\n")


if __name__ == "__main__":
    main()
