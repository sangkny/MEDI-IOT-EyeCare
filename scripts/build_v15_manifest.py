#!/usr/bin/env python3
"""
파일명: scripts/build_v15_manifest.py
목적:   unified_v14.json → unified_v15.json (glaucoma_grade 라벨 전 샘플 보강)

- 한국인 임상: glaucoma_grade 1/2/3 (실제 grade, v14와 동일)
- 공개셋 GL 음성: glaucoma_grade=0
- 공개셋 GL 양성: glaucoma_grade=1 (세분화 불가 근사)
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = ROOT / "training/manifests/unified_v14.json"
DEFAULT_OUTPUT = ROOT / "training/manifests/unified_v15.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def enrich_grades(manifest: dict) -> dict:
    samples = manifest.get("samples") or []
    grade_counts: Counter[int] = Counter()
    korean_grade_counts: Counter[int] = Counter()

    for s in samples:
        labels = dict(s.get("available_labels") or {})
        if s.get("korean_clinical") and "glaucoma_grade" in labels:
            g = int(labels["glaucoma_grade"])
            korean_grade_counts[g] += 1
        elif "glaucoma_grade" not in labels:
            if "glaucoma" in labels:
                labels["glaucoma_grade"] = 0 if int(labels["glaucoma"]) == 0 else 1
            else:
                labels["glaucoma_grade"] = 0
        s["available_labels"] = labels
        grade_counts[int(labels["glaucoma_grade"])] += 1

    out = dict(manifest)
    out.update({
        "task": "v15",
        "version": "v15",
        "total": len(samples),
        "grade_label_policy": {
            "korean_clinical": "grade 1/2/3 from labels_modified.csv",
            "public_gl_negative": "grade 0",
            "public_gl_positive": "grade 1 (no severity split)",
        },
        "grade_distribution": {str(k): v for k, v in sorted(grade_counts.items())},
        "korean_grade_distribution": {str(k): v for k, v in sorted(korean_grade_counts.items())},
        "samples": samples,
    })
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base", type=Path, default=DEFAULT_BASE)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = p.parse_args()

    base_path = args.base if args.base.is_absolute() else ROOT / args.base
    if not base_path.is_file():
        print(f"error: base manifest missing: {base_path}", file=sys.stderr)
        print("  → python3 scripts/build_v14_manifest.py first", file=sys.stderr)
        sys.exit(1)

    manifest = enrich_grades(_load_json(base_path))
    out_path = args.output if args.output.is_absolute() else ROOT / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"OK {out_path}")
    print(f"total={manifest['total']} grade_dist={manifest['grade_distribution']}")
    print(f"korean_grade={manifest['korean_grade_distribution']}")


if __name__ == "__main__":
    main()
