#!/usr/bin/env python3
"""unified_v10.json — 5 manifest 병합 (path dedup + available_labels)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from training.make_manifest import MULTIDISEASE_TRAIN_CLASSES


def normalize_dr_path(path: str, *, dr_data_dir: str = "/data_dr") -> str:
    """DR manifest 경로 → Docker /data_dr/resized_cache/... 절대경로."""
    key = path.replace("\\", "/")
    if key.startswith("/data_dr/"):
        return key
    stripped = key.lstrip("/")
    if stripped.startswith("data/"):
        stripped = stripped[5:]
    if "/resized_cache/" in stripped:
        idx = stripped.index("resized_cache/")
        return f"{dr_data_dir.rstrip('/')}/{stripped[idx:]}"
    if stripped.startswith("resized_cache/"):
        return f"{dr_data_dir.rstrip('/')}/{stripped}"
    return f"{dr_data_dir.rstrip('/')}/resized_cache/{stripped}"


def _load_manifest(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _samples(manifest: dict) -> list[dict]:
    if manifest.get("samples"):
        return list(manifest["samples"])
    out: list[dict] = []
    for key in ("train", "val", "test"):
        for s in manifest.get(key) or []:
            item = dict(s)
            item.setdefault("split", key)
            out.append(item)
    return out


def merge_v10_manifests(
    *,
    dr_path: Path,
    glaucoma_path: Path,
    amd_path: Path,
    myopia_path: Path,
    multidisease_path: Path,
    data_dir: str = "/dataset",
    dr_data_dir: str = "/data_dr",
) -> dict:
    merged: dict[str, dict] = {}

    def upsert(path: str, split: str, patch: dict) -> None:
        key = path.replace("\\", "/")
        row = merged.get(key)
        if row is None:
            row = {
                "path": key,
                "split": split,
                "available_labels": {},
            }
            merged[key] = row
        row["available_labels"].update(patch)
        if split:
            row["split"] = split

    for s in _samples(_load_manifest(dr_path)):
        if s.get("dr_grade") is None:
            continue
        dr_path_norm = normalize_dr_path(str(s["path"]), dr_data_dir=dr_data_dir)
        upsert(dr_path_norm, s.get("split", "train"), {"dr": int(s["dr_grade"])})

    for s in _samples(_load_manifest(glaucoma_path)):
        label = s.get("glaucoma_grade", s.get("label"))
        if label is None:
            continue
        upsert(s["path"], s.get("split", "train"), {"glaucoma": int(label)})

    for s in _samples(_load_manifest(amd_path)):
        label = s.get("amd_grade", s.get("label"))
        if label is None:
            continue
        upsert(s["path"], s.get("split", "train"), {"amd": int(label)})

    for s in _samples(_load_manifest(myopia_path)):
        label = s.get("myopia_grade", s.get("label"))
        if label is None:
            continue
        upsert(s["path"], s.get("split", "train"), {"myopia": int(label)})

    multi_data = _load_manifest(multidisease_path)
    class_names = tuple(multi_data.get("label_classes") or MULTIDISEASE_TRAIN_CLASSES)
    for s in _samples(multi_data):
        labels = s.get("labels") or {}
        if not labels:
            continue
        multi = {name: int(labels.get(name, 0)) for name in class_names}
        upsert(s["path"], s.get("split", "train"), {"multidisease": multi})

    samples = list(merged.values())
    splits = {"train": 0, "val": 0, "test": 0}
    label_counts = {"dr": 0, "glaucoma": 0, "amd": 0, "myopia": 0, "multidisease": 0}
    for s in samples:
        splits[s.get("split", "train")] = splits.get(s.get("split", "train"), 0) + 1
        al = s.get("available_labels") or {}
        for k in label_counts:
            if k in al:
                label_counts[k] += 1

    return {
        "data_dir": data_dir,
        "dr_data_dir": dr_data_dir,
        "task": "v10",
        "total": len(samples),
        "label_classes": list(class_names),
        "splits": splits,
        "label_coverage": label_counts,
        "sources": {
            "dr_manifest": dr_path.name,
            "glaucoma_manifest": glaucoma_path.name,
            "amd_manifest": amd_path.name,
            "myopia_manifest": myopia_path.name,
            "multidisease_manifest": multidisease_path.name,
        },
        "samples": samples,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Merge 5 manifests → unified_v10.json")
    p.add_argument("--dr", type=Path, default=ROOT / "training/manifests/unified_v4.json")
    p.add_argument("--glaucoma", type=Path, default=ROOT / "training/manifests/glaucoma_v2.json")
    p.add_argument("--amd", type=Path, default=ROOT / "training/manifests/amd_v1.json")
    p.add_argument("--myopia", type=Path, default=ROOT / "training/manifests/myopia_v1.json")
    p.add_argument("--multidisease", type=Path, default=ROOT / "training/manifests/multidisease_v1.json")
    p.add_argument("--output", type=Path, default=ROOT / "training/manifests/unified_v10.json")
    p.add_argument("--data-dir", dest="data_dir", default="/dataset")
    p.add_argument("--dr-data-dir", dest="dr_data_dir", default="/data_dr")
    args = p.parse_args()

    manifest = merge_v10_manifests(
        dr_path=args.dr if args.dr.is_absolute() else ROOT / args.dr,
        glaucoma_path=args.glaucoma if args.glaucoma.is_absolute() else ROOT / args.glaucoma,
        amd_path=args.amd if args.amd.is_absolute() else ROOT / args.amd,
        myopia_path=args.myopia if args.myopia.is_absolute() else ROOT / args.myopia,
        multidisease_path=args.multidisease if args.multidisease.is_absolute() else ROOT / args.multidisease,
        data_dir=args.data_dir,
        dr_data_dir=args.dr_data_dir,
    )
    out = args.output if args.output.is_absolute() else ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"OK {out} total={manifest['total']} "
        f"splits={manifest['splits']} coverage={manifest['label_coverage']}"
    )


if __name__ == "__main__":
    main()
