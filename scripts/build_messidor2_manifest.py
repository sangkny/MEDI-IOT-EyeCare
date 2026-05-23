#!/usr/bin/env python3
"""이미지 디렉터리 → train/val/test manifest JSON."""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SPLITS = ("train", "val", "test")


def _scan_split(data_dir: Path, split: str) -> list[dict]:
    entries: list[dict] = []
    split_dir = data_dir / "images" / split
    if not split_dir.is_dir():
        return entries
    for grade_dir in sorted(split_dir.iterdir()):
        if not grade_dir.is_dir():
            continue
        try:
            grade = int(grade_dir.name)
        except ValueError:
            continue
        for img in sorted(grade_dir.glob("*.jpg")) + sorted(grade_dir.glob("*.png")):
            rel = img.relative_to(data_dir).as_posix()
            entries.append({"path": rel, "dr_grade": grade})
    return entries


def build_manifest(data_dir: Path, *, source: str = "messidor2") -> dict:
    data_dir = data_dir.resolve()
    try:
        data_dir_key = str(data_dir.relative_to(ROOT))
    except ValueError:
        data_dir_key = str(data_dir)
    manifest = {
        "data_dir": data_dir_key,
        "source": source,
        "train": _scan_split(data_dir, "train"),
        "val": _scan_split(data_dir, "val"),
        "test": _scan_split(data_dir, "test"),
    }
    if not manifest["train"] and (data_dir / "images").is_dir():
        all_entries = []
        for grade_dir in sorted((data_dir / "images").iterdir()):
            if not grade_dir.is_dir():
                continue
            try:
                grade = int(grade_dir.name)
            except ValueError:
                continue
            for img in grade_dir.glob("*.jpg"):
                all_entries.append(
                    {"path": img.relative_to(data_dir).as_posix(), "dr_grade": grade}
                )
        random.shuffle(all_entries)
        n = len(all_entries)
        manifest["train"] = all_entries[: int(n * 0.8)]
        manifest["val"] = all_entries[int(n * 0.8) : int(n * 0.9)]
        manifest["test"] = all_entries[int(n * 0.9) :]
    return manifest


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", "--data_dir", dest="data_dir", type=Path, required=True)
    p.add_argument("--output", "-o", type=Path, required=True)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--source", default="messidor2", help="manifest source label")
    args = p.parse_args()

    data_dir = args.data_dir
    if not data_dir.is_absolute():
        data_dir = ROOT / data_dir
    out = args.output
    if not out.is_absolute():
        out = ROOT / out

    random.seed(args.seed)
    manifest = build_manifest(data_dir, source=args.source)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    for s in SPLITS:
        print(f"{s}: {len(manifest.get(s) or [])} entries")
    print(f"OK {out}")


if __name__ == "__main__":
    main()
