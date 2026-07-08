#!/usr/bin/env python3
"""
파일명: scripts/build_v14_manifest.py
목적:   unified_v10.json + 한국인 임상 데이터 → unified_v14.json

IRB: 국내 임상기관 IRB 승인 (2019) — 로컬 전용
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path

IRB_INFO = {
    "institution": "Korean Clinical Institution",
    "approved_year": 2019,
    "storage_policy": "LOCAL_ONLY",
}

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = ROOT / "training/manifests/unified_v10.json"
DEFAULT_OUTPUT = ROOT / "training/manifests/unified_v14.json"
KOREAN_ROOT = Path("/dataset/korean_glaucoma_fundus")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _korean_sample(
    rel_path: str,
    *,
    split: str,
    grade: int,
    is_ntg: int,
    is_poag: int,
    is_pacg: int,
    source: str,
) -> dict:
    return {
        "path": rel_path,
        "split": split,
        "source": source,
        "korean_clinical": True,
        "available_labels": {
            "glaucoma": 1,
            "glaucoma_grade": grade,
            "is_ntg": is_ntg,
            "is_poag": is_poag,
            "is_pacg": is_pacg,
        },
    }


def _assign_split(seed: int, key: str) -> str:
    rng = random.Random(f"{seed}:{key}")
    r = rng.random()
    if r < 0.15:
        return "val"
    if r < 0.30:
        return "test"
    return "train"


def load_korean_from_csv(
    csv_path: Path,
    path_prefix: str,
    *,
    source: str,
    seed: int,
) -> list[dict]:
    if not csv_path.is_file():
        return []

    samples: list[dict] = []
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("modality") not in ("color", None) and row.get("file_type") == "fundus":
                pass
            if row.get("modality") == "ir":
                continue
            if row.get("file_type") and row.get("file_type") != "fundus":
                continue
            if row.get("modality") and row.get("modality") != "color":
                continue

            fname = row.get("filename", "")
            if not fname:
                continue

            if "modified" in path_prefix:
                eye = row.get("eye", "R")
                sub = "OD" if eye == "R" else "OS"
                rel = f"{path_prefix}/color/{sub}/{fname}"
            else:
                eye = row.get("eye", "R")
                if eye == "OU":
                    continue
                sub = "OD" if eye == "R" else "OS"
                rel = f"{path_prefix}/fundus/{sub}/{fname}"

            grade = int(row.get("grade", row.get("glaucoma_grade", 1)) or 1)
            key = row.get("image_no") or row.get("folder_no") or fname
            samples.append(
                _korean_sample(
                    rel,
                    split=_assign_split(seed, str(key)),
                    grade=grade,
                    is_ntg=int(row.get("is_ntg", 0) or 0),
                    is_poag=int(row.get("is_poag", 0) or 0),
                    is_pacg=int(row.get("is_pacg", 0) or 0),
                    source=source,
                )
            )
    return samples


def merge_v14(base: dict, korean_samples: list[dict]) -> dict:
    merged: dict[str, dict] = {}
    for s in base.get("samples") or []:
        key = str(s["path"]).replace("\\", "/")
        merged[key] = {
            "path": key,
            "split": s.get("split", "train"),
            "available_labels": dict(s.get("available_labels") or {}),
        }
        if s.get("source"):
            merged[key]["source"] = s["source"]

    added = 0
    for s in korean_samples:
        key = s["path"]
        if key in merged:
            merged[key]["available_labels"].update(s["available_labels"])
            merged[key]["korean_clinical"] = True
        else:
            merged[key] = s
            added += 1

    samples = list(merged.values())
    splits = Counter(s.get("split", "train") for s in samples)
    korean_n = sum(1 for s in samples if s.get("korean_clinical"))

    out = dict(base)
    out.update({
        "task": "v14",
        "version": "v14",
        "total": len(samples),
        "splits": dict(splits),
        "irb_korean_clinical": IRB_INFO,
        "sources": {
            **(base.get("sources") or {}),
            "korean_modified": "labels_modified.csv",
            "korean_origin_fundus": "labels_origin.csv",
        },
        "korean_clinical_count": korean_n,
        "korean_added": added,
        "samples": samples,
    })
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base", type=Path, default=DEFAULT_BASE)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--korean-root", type=Path, default=KOREAN_ROOT)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    base_path = args.base if args.base.is_absolute() else ROOT / args.base
    if not base_path.is_file():
        print(f"error: base manifest missing: {base_path}", file=sys.stderr)
        sys.exit(1)

    base = _load_json(base_path)
    korean: list[dict] = []
    korean.extend(
        load_korean_from_csv(
            args.korean_root / "labels_modified.csv",
            "korean_glaucoma_fundus/modified",
            source="korean_modified",
            seed=args.seed,
        )
    )
    korean.extend(
        load_korean_from_csv(
            args.korean_root / "labels_origin.csv",
            "korean_glaucoma_fundus/origin",
            source="korean_origin",
            seed=args.seed + 1,
        )
    )

    manifest = merge_v14(base, korean)
    out_path = args.output if args.output.is_absolute() else ROOT / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"OK {out_path}")
    print(f"total={manifest['total']} korean={manifest['korean_clinical_count']} added={manifest['korean_added']}")
    print(f"splits={manifest['splits']}")


if __name__ == "__main__":
    main()
