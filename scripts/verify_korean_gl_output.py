#!/usr/bin/env python3
"""
파일명: scripts/verify_korean_gl_output.py
목적:   전처리 결과 품질 검증

IRB: 국내 임상기관 IRB 승인 (2019)
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
from collections import Counter
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

DEFAULT_OUTPUT = Path("/dataset/korean_glaucoma_fundus")
GREEN_G_MIN = 80
GREEN_RATIO = 1.4
MIN_FILE_BYTES = 1024
SAMPLE_COUNT = 20


def count_green_pixels(img: np.ndarray) -> int:
    r = img[:, :, 2].astype(float)
    g = img[:, :, 1].astype(float)
    b = img[:, :, 0].astype(float)
    green = (g > GREEN_G_MIN) & (g > r * GREEN_RATIO) & (g > b * GREEN_RATIO)
    return int(green.sum())


def collect_images(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [p for p in root.rglob("*.jpg") if p.is_file()]


def verify_output(output_dir: Path) -> int:
    print("=" * 60)
    print("Korean glaucoma output verification")
    print(f"IRB: {IRB_INFO['institution']} ({IRB_INFO['approved_year']})")
    print(f"Output: {output_dir}")
    print()

    errors = 0
    subsets = {
        "modified": output_dir / "modified",
        "origin": output_dir / "origin",
    }

    for name, subset_dir in subsets.items():
        images = collect_images(subset_dir)
        print(f"[{name}] images: {len(images)}")
        if not images:
            print(f"  warn: no images under {subset_dir}")
            continue

        small = [p for p in images if p.stat().st_size < MIN_FILE_BYTES]
        if small:
            errors += len(small)
            print(f"  error: {len(small)} files below {MIN_FILE_BYTES} bytes")

        sample = random.sample(images, min(SAMPLE_COUNT, len(images)))
        green_hits = 0
        for path in sample:
            img = cv2.imread(str(path))
            if img is None:
                errors += 1
                print(f"  error: cannot read {path.name}")
                continue
            if count_green_pixels(img) > 50:
                green_hits += 1
                print(f"  warn: green text remnant in {path.name}")

        print(f"  green remnant check: {green_hits}/{len(sample)} sampled")

    for label_name in ("labels_modified.csv", "labels_origin.csv"):
        label_path = output_dir / label_name
        if not label_path.exists():
            print(f"[labels] missing: {label_name}")
            continue
        with open(label_path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        print(f"[{label_name}] rows: {len(rows)}")
        if "grade" in (rows[0].keys() if rows else []):
            grades = Counter(int(r.get("grade", 0)) for r in rows)
            print(f"  grade distribution: {dict(sorted(grades.items()))}")
        if "diagnosis" in (rows[0].keys() if rows else []):
            diag = Counter(r.get("diagnosis", "") for r in rows)
            top = diag.most_common(5)
            print(f"  top diagnoses: {top}")

    manifest_files = list(output_dir.glob("manifest_*.json"))
    print(f"[manifest] files: {len(manifest_files)}")

    print()
    if errors:
        print(f"FAILED with {errors} error(s)")
        return 1
    print("PASSED")
    return 0


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = p.parse_args()

    if not args.output_dir.exists():
        print(f"error: missing {args.output_dir}", file=sys.stderr)
        sys.exit(1)

    sys.exit(verify_output(args.output_dir))


if __name__ == "__main__":
    main()
