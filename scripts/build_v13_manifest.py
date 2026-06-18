#!/usr/bin/env python3
"""
파일명: scripts/build_v13_manifest.py
목적: unified_v12 기반 + GT/pseudo disc_cup_mask 통합 → unified_v13.json
      GL 마스크 커버리지 70%+ 목표
히스토리:
  2026-06-19 - 최초 작성
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def _image_stem(path: str) -> str:
    return Path(path.replace("\\", "/")).stem


# 우선순위: GT G1020 > pseudo G1020 > manifest pseudo > 기타 pseudo
MASK_SUBDIRS = (
    "G1020",
    "pseudo/G1020",
    "pseudo/manifest",
    "pseudo/RIM-ONE",
    "pseudo/Glaucoma_extra",
    "RIM-ONE",
    "Glaucoma_extra",
)


def _find_mask(stem: str, dataset_root: Path) -> str | None:
    for sub in MASK_SUBDIRS:
        rel = f"disc_cup_masks/{sub}/{stem}_mask.png"
        if (dataset_root / rel).is_file():
            return rel
    return None


def build_v13_manifest(
    *,
    base_manifest: Path,
    dataset_root: Path,
    out_path: Path,
) -> dict[str, int | float]:
    data = _load_json(base_manifest)
    samples = data.get("samples") or []
    mask_hits = 0
    gl_total = 0
    gl_with_mask = 0
    pseudo_hits = 0

    for entry in samples:
        stem = _image_stem(str(entry.get("path", "")))
        found = _find_mask(stem, dataset_root)
        if found:
            entry["disc_cup_mask"] = found
            entry["disc_cup_mask_source"] = "gt" if found.startswith("disc_cup_masks/G1020") else "pseudo"
            mask_hits += 1
            if entry["disc_cup_mask_source"] == "pseudo":
                pseudo_hits += 1
        else:
            entry["disc_cup_mask"] = None
            entry.pop("disc_cup_mask_source", None)

        al = entry.get("available_labels") or {}
        if "glaucoma" in al:
            gl_total += 1
            if entry.get("disc_cup_mask"):
                gl_with_mask += 1

    out = dict(data)
    out["version"] = "v13"
    out["base_manifest"] = base_manifest.name
    out["seg_mask_note"] = "GT G1020 + SAM pseudo; null → seg loss skip"
    out["samples"] = samples
    _dump_json(out_path, out)

    gl_pct = 100.0 * gl_with_mask / gl_total if gl_total else 0.0
    return {
        "total": len(samples),
        "mask_hits": mask_hits,
        "pseudo_hits": pseudo_hits,
        "gl_total": gl_total,
        "gl_with_mask": gl_with_mask,
        "gl_pct": gl_pct,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="unified_v12 → unified_v13 (+ SAM pseudo masks)")
    p.add_argument("--base", type=Path, default=ROOT / "training/manifests/unified_v12.json")
    p.add_argument("--dataset-root", type=Path, default=Path("/dataset"))
    p.add_argument("--out", type=Path, default=ROOT / "training/manifests/unified_v13.json")
    args = p.parse_args()

    base = args.base if args.base.is_absolute() else ROOT / args.base
    out = args.out if args.out.is_absolute() else ROOT / args.out
    stats = build_v13_manifest(
        base_manifest=base,
        dataset_root=args.dataset_root,
        out_path=out,
    )
    print(
        f"v13 manifest → {out}\n"
        f"  samples={stats['total']} mask_hits={stats['mask_hits']} pseudo={stats['pseudo_hits']}\n"
        f"  GL={stats['gl_total']} GL+mask={stats['gl_with_mask']} ({stats['gl_pct']:.1f}%)"
    )
    if stats["gl_pct"] < 70.0:
        print("WARN: GL mask coverage < 70% — run generate_pseudo_masks_sam.py --phase manifest")


if __name__ == "__main__":
    main()
