#!/usr/bin/env python3
"""
파일명: build_gl_extra2_manifest.py
목적: GL extra2 (G1020 / ORIGA / ACRIMA) 라벨 파싱 → manifest JSON
실행: Docker 컨테이너 내부 (docs/DOCKER-POLICY.md)
  docker run --rm \\
    -v ~/workspace/dataset:/dataset \\
    -v $REPO:/workspace \\
    medi-train:gpu \\
    bash -c 'python3 /workspace/scripts/build_gl_extra2_manifest.py'
히스토리:
  2026-06-13 - 최초 작성 (G1020+ORIGA+ACRIMA 2,375장)
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


@dataclass
class SourceStats:
    name: str
    total: int = 0
    normal: int = 0
    abnormal: int = 0
    missing: int = 0
    splits: Counter = field(default_factory=Counter)


def _assign_split(key: str, *, val_ratio: float = 0.15, test_ratio: float = 0.15) -> str:
    h = hash(key) & 0xFFFFFFFF
    r = (h % 10_000) / 10_000.0
    if r < test_ratio:
        return "test"
    if r < test_ratio + val_ratio:
        return "val"
    return "train"


def _rel_path(data_root: Path, file_path: Path, *, path_root: str) -> str:
    rel = file_path.relative_to(data_root).as_posix()
    if path_root == "enhanced_cache":
        return f"enhanced_cache/{rel}"
    return rel


def _sample(
    data_root: Path,
    image_path: Path,
    label: int,
    *,
    source: str,
    path_root: str,
) -> dict | None:
    if not image_path.is_file():
        return None
    rel = _rel_path(data_root, image_path, path_root=path_root)
    split = _assign_split(f"{source}:{rel}")
    return {
        "path": rel,
        "split": split,
        "source": source,
        "available_labels": {"glaucoma": int(label)},
    }


def parse_g1020(data_root: Path, *, path_root: str) -> tuple[list[dict], SourceStats]:
    stats = SourceStats("G1020")
    samples: list[dict] = []
    csv_path = data_root / "Glaucoma_extra2/G1020/G1020/G1020.csv"
    img_dir = data_root / "Glaucoma_extra2/G1020/G1020/Images"
    if not csv_path.is_file():
        print(f"WARN: G1020 csv missing: {csv_path}")
        return samples, stats
    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            image_id = (row.get("imageID") or row.get("ImageID") or "").strip()
            raw_label = row.get("binaryLabels") or row.get("BinaryLabels") or row.get("label")
            if not image_id or raw_label is None:
                continue
            label = int(float(raw_label))
            img_path = img_dir / image_id
            if not img_path.is_file() and img_path.suffix.lower() not in IMAGE_EXTS:
                for ext in IMAGE_EXTS:
                    alt = img_dir / f"{Path(image_id).stem}{ext}"
                    if alt.is_file():
                        img_path = alt
                        break
            row_sample = _sample(data_root, img_path, label, source="g1020", path_root=path_root)
            if row_sample is None:
                stats.missing += 1
                continue
            samples.append(row_sample)
            stats.total += 1
            stats.splits[row_sample["split"]] += 1
            if label == 0:
                stats.normal += 1
            else:
                stats.abnormal += 1
    return samples, stats


def parse_origa(data_root: Path, *, path_root: str) -> tuple[list[dict], SourceStats]:
    stats = SourceStats("ORIGA")
    samples: list[dict] = []
    csv_path = data_root / "Glaucoma_extra2/G1020/ORIGA/OrigaList.csv"
    img_dir = data_root / "Glaucoma_extra2/G1020/ORIGA/Images"
    if not csv_path.is_file():
        print(f"WARN: ORIGA csv missing: {csv_path}")
        return samples, stats
    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            filename = (row.get("Filename") or row.get("filename") or "").strip()
            raw_label = row.get("Glaucoma") or row.get("glaucoma") or row.get("label")
            if not filename or raw_label is None:
                continue
            label = int(float(raw_label))
            img_path = img_dir / filename
            row_sample = _sample(data_root, img_path, label, source="origa", path_root=path_root)
            if row_sample is None:
                stats.missing += 1
                continue
            samples.append(row_sample)
            stats.total += 1
            stats.splits[row_sample["split"]] += 1
            if label == 0:
                stats.normal += 1
            else:
                stats.abnormal += 1
    return samples, stats


def parse_acrima(data_root: Path, *, path_root: str) -> tuple[list[dict], SourceStats]:
    stats = SourceStats("ACRIMA")
    samples: list[dict] = []
    img_dir = data_root / "Glaucoma_extra2/ORIGA/ACRIMA/Images"
    if not img_dir.is_dir():
        print(f"WARN: ACRIMA dir missing: {img_dir}")
        return samples, stats
    for img_path in sorted(img_dir.rglob("*")):
        if img_path.suffix.lower() not in IMAGE_EXTS:
            continue
        label = 1 if "_g_" in img_path.name.lower() else 0
        row_sample = _sample(data_root, img_path, label, source="acrima", path_root=path_root)
        if row_sample is None:
            stats.missing += 1
            continue
        samples.append(row_sample)
        stats.total += 1
        stats.splits[row_sample["split"]] += 1
        if label == 0:
            stats.normal += 1
        else:
            stats.abnormal += 1
    return samples, stats


def _print_stats(all_stats: list[SourceStats]) -> None:
    total = sum(s.total for s in all_stats)
    normal = sum(s.normal for s in all_stats)
    abnormal = sum(s.abnormal for s in all_stats)
    for st in all_stats:
        miss = f" missing={st.missing}" if st.missing else ""
        print(
            f"{st.name}: total={st.total} normal={st.normal} abnormal={st.abnormal}{miss} "
            f"splits={dict(st.splits)}"
        )
    print(f"TOTAL: {total} normal={normal} abnormal={abnormal}")


def build_manifest(data_root: Path, *, path_root: str) -> tuple[dict, list[SourceStats]]:
    parts: list[dict] = []
    stats_list: list[SourceStats] = []
    for parser in (parse_g1020, parse_origa, parse_acrima):
        rows, st = parser(data_root, path_root=path_root)
        parts.extend(rows)
        stats_list.append(st)

    splits = Counter(s.get("split", "train") for s in parts)
    gl_normal = sum(1 for s in parts if s["available_labels"]["glaucoma"] == 0)
    gl_abnormal = sum(1 for s in parts if s["available_labels"]["glaucoma"] == 1)

    manifest = {
        "data_dir": "/dataset",
        "task": "glaucoma_extra2",
        "total": len(parts),
        "sources": ["g1020", "origa", "acrima"],
        "splits": dict(splits),
        "label_coverage": {"glaucoma": len(parts)},
        "glaucoma_balance": {"normal": gl_normal, "abnormal": gl_abnormal},
        "path_root": path_root,
        "samples": parts,
    }
    return manifest, stats_list


def main() -> None:
    p = argparse.ArgumentParser(description="Build gl_extra2.json from G1020/ORIGA/ACRIMA")
    p.add_argument("--data-root", type=Path, default=Path("/dataset"))
    p.add_argument(
        "--path-root",
        choices=("Glaucoma_extra2", "enhanced_cache"),
        default="Glaucoma_extra2",
        help="manifest path prefix (enhanced_cache after preprocess_enhanced)",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=ROOT / "training/manifests/gl_extra2.json",
    )
    args = p.parse_args()

    data_root = args.data_root
    if not data_root.is_dir():
        print(f"WARN: data-root not found: {data_root} (writing empty manifest)")

    manifest, stats_list = build_manifest(data_root, path_root=args.path_root)
    _print_stats(stats_list)

    out = args.output if args.output.is_absolute() else ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK → {out} total={manifest['total']}")


if __name__ == "__main__":
    main()
