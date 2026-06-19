#!/usr/bin/env python3
"""
파일명: scripts/build_v13_manifest.py
목적: unified_v12 기반 + GT disc_cup_mask (G1020 + ORIGA) → unified_v13.json
      v13 Plan B — pseudo-mask 없이 실제 GT만 (GL 마스크 ~14.3%)
히스토리:
  2026-06-19 - 최초 작성 (SAM pseudo 경로)
  2026-06-19 - Plan B: G1020 + ORIGA GT only
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Plan B: GT only (G1020 우선, ORIGA)
GT_MASK_SUBDIRS: tuple[tuple[str, str], ...] = (
    ("G1020", "gt_g1020"),
    ("ORIGA", "gt_origa"),
)

# SAM pseudo 경로 (Plan B 아닐 때만)
PSEUDO_MASK_SUBDIRS = (
    "pseudo_osam/G1020",
    "pseudo_osam/manifest",
    "pseudo/G1020",
    "pseudo/manifest",
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def _image_stem(path: str) -> str:
    return Path(path.replace("\\", "/")).stem


def _find_gt_mask(stem: str, dataset_root: Path) -> tuple[str, str] | None:
    for sub, source in GT_MASK_SUBDIRS:
        rel = f"disc_cup_masks/{sub}/{stem}_mask.png"
        if (dataset_root / rel).is_file():
            return rel, source
    return None


def _find_pseudo_mask(stem: str, dataset_root: Path) -> str | None:
    for sub in PSEUDO_MASK_SUBDIRS:
        rel = f"disc_cup_masks/{sub}/{stem}_mask.png"
        if (dataset_root / rel).is_file():
            return rel
    return None


def build_v13_manifest(
    *,
    base_manifest: Path,
    dataset_root: Path,
    out_path: Path,
    plan_b: bool = True,
) -> dict[str, int | float]:
    data = _load_json(base_manifest)
    samples = data.get("samples") or []
    mask_hits = 0
    gl_total = 0
    gl_with_mask = 0
    g1020_hits = origa_hits = pseudo_hits = 0

    for entry in samples:
        stem = _image_stem(str(entry.get("path", "")))
        found: tuple[str, str] | None = None
        gt = _find_gt_mask(stem, dataset_root)
        if gt:
            found = gt
            if gt[1] == "gt_g1020":
                g1020_hits += 1
            else:
                origa_hits += 1
        elif not plan_b:
            pseudo = _find_pseudo_mask(stem, dataset_root)
            if pseudo:
                found = (pseudo, "pseudo")

        if found:
            entry["disc_cup_mask"] = found[0]
            entry["disc_cup_mask_source"] = found[1]
            mask_hits += 1
            if found[1] == "pseudo":
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
    if plan_b:
        out["seg_mask_note"] = "Plan B: GT G1020 + ORIGA only; null → seg loss skip"
        out["plan_b"] = True
    else:
        out["seg_mask_note"] = "GT G1020 + SAM pseudo; null → seg loss skip"
        out["plan_b"] = False
    out["samples"] = samples
    _dump_json(out_path, out)

    gl_pct = 100.0 * gl_with_mask / gl_total if gl_total else 0.0
    return {
        "total": len(samples),
        "mask_hits": mask_hits,
        "g1020_hits": g1020_hits,
        "origa_hits": origa_hits,
        "pseudo_hits": pseudo_hits,
        "gl_total": gl_total,
        "gl_with_mask": gl_with_mask,
        "gl_pct": gl_pct,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="unified_v12 → unified_v13 (+ disc/cup masks)")
    p.add_argument("--base", type=Path, default=ROOT / "training/manifests/unified_v12.json")
    p.add_argument("--dataset-root", type=Path, default=Path("/dataset"))
    p.add_argument("--out", type=Path, default=ROOT / "training/manifests/unified_v13.json")
    p.add_argument(
        "--plan-b",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="GT G1020+ORIGA only (default). --no-plan-b enables SAM pseudo fallback",
    )
    args = p.parse_args()

    base = args.base if args.base.is_absolute() else ROOT / args.base
    out = args.out if args.out.is_absolute() else ROOT / args.out
    stats = build_v13_manifest(
        base_manifest=base,
        dataset_root=args.dataset_root,
        out_path=out,
        plan_b=args.plan_b,
    )
    mode = "Plan B (GT only)" if args.plan_b else "pseudo+GT"
    print(f"v13 manifest [{mode}] → {out}")
    print(
        f"  samples={stats['total']} mask_hits={stats['mask_hits']} "
        f"(g1020={stats['g1020_hits']} origa={stats['origa_hits']} pseudo={stats['pseudo_hits']})"
    )
    print(f"  GL={stats['gl_total']} GL+mask={stats['gl_with_mask']} ({stats['gl_pct']:.1f}%)")
    if args.plan_b and stats["gl_pct"] < 14.0:
        print("WARN: GL mask coverage < 14% — run build_disc_cup_masks.py --origa")


if __name__ == "__main__":
    main()
