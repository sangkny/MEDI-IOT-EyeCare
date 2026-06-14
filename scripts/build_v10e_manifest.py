#!/usr/bin/env python3
"""
파일명: build_v10e_manifest.py
목적: unified_v10.json + gl_extra2.json → unified_v10e.json
히스토리:
  2026-06-13 - 최초 작성

실행 (Docker):
  docker run --rm \\
    -v ~/workspace/dataset:/dataset \\
    -v $REPO:/workspace \\
    medi-train:gpu \\
    bash -c 'python3 /workspace/scripts/build_v10e_manifest.py'
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _gl_stats(samples: list[dict]) -> tuple[int, int, int]:
    gl = [s for s in samples if "glaucoma" in (s.get("available_labels") or {})]
    normal = sum(1 for s in gl if s["available_labels"]["glaucoma"] == 0)
    abnormal = sum(1 for s in gl if s["available_labels"]["glaucoma"] == 1)
    return len(gl), normal, abnormal


def merge_v10e(
    base: dict,
    extra2: dict,
    *,
    extra2_use_enhanced: bool = False,
    use_v2_cache: bool = False,
) -> dict:
    merged: dict[str, dict] = {}

    def _rewrite_path(path: str) -> str:
        key = path.replace("\\", "/")
        if use_v2_cache:
            key = key.replace("/data_dr/resized_cache/", "/data_dr/v2_cache/")
            key = key.replace("resized_cache/", "v2_cache/")
            key = key.replace("enhanced_cache/", "v2_cache/")
        elif extra2_use_enhanced and key.startswith("Glaucoma_extra2/"):
            key = f"enhanced_cache/{key}"
        return key

    for s in base.get("samples") or []:
        key = _rewrite_path(str(s["path"]))
        merged[key] = {
            "path": key,
            "split": s.get("split", "train"),
            "available_labels": dict(s.get("available_labels") or {}),
        }
        if s.get("source"):
            merged[key]["source"] = s["source"]

    base_gl, _, _ = _gl_stats(list(merged.values()))
    added = 0
    updated = 0

    for s in extra2.get("samples") or []:
        key = _rewrite_path(str(s["path"]))
        if extra2_use_enhanced and not use_v2_cache and key.startswith("Glaucoma_extra2/"):
            key = f"enhanced_cache/{key}"
        label = int(s["available_labels"]["glaucoma"])
        if key in merged:
            merged[key]["available_labels"]["glaucoma"] = label
            updated += 1
        else:
            merged[key] = {
                "path": key,
                "split": s.get("split", "train"),
                "source": s.get("source", "extra2"),
                "available_labels": {"glaucoma": label},
            }
            added += 1

    samples = list(merged.values())
    splits = Counter(s.get("split", "train") for s in samples)
    coverage = Counter()
    for s in samples:
        for k in s.get("available_labels") or {}:
            coverage[k] += 1

    gl_total, gl_normal, gl_abnormal = _gl_stats(samples)

    out = dict(base)
    out.update(
        {
            "task": "v10e",
            "total": len(samples),
            "splits": dict(splits),
            "label_coverage": dict(coverage),
            "sources": {
                **(base.get("sources") or {}),
                "gl_extra2_manifest": "gl_extra2.json",
            },
            "glaucoma_stats": {
                "base_gl_count": base_gl,
                "extra2_added": added,
                "extra2_updated": updated,
                "total_gl": gl_total,
                "normal": gl_normal,
                "abnormal": gl_abnormal,
            },
            "samples": samples,
        }
    )
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Merge unified_v10 + gl_extra2 → unified_v10e")
    p.add_argument("--base", type=Path, default=ROOT / "training/manifests/unified_v10.json")
    p.add_argument("--extra2", type=Path, default=ROOT / "training/manifests/gl_extra2.json")
    p.add_argument("--output", type=Path, default=ROOT / "training/manifests/unified_v10e.json")
    p.add_argument(
        "--extra2-enhanced-paths",
        action="store_true",
        help="prefix extra2 paths with enhanced_cache/ (legacy v1)",
    )
    p.add_argument(
        "--v2-cache-paths",
        action="store_true",
        help="rewrite all paths to v2_cache/ (after preprocess_v2)",
    )
    args = p.parse_args()

    base_path = args.base if args.base.is_absolute() else ROOT / args.base
    extra2_path = args.extra2 if args.extra2.is_absolute() else ROOT / args.extra2
    if not base_path.is_file():
        raise SystemExit(f"FAIL: base manifest missing: {base_path}")
    if not extra2_path.is_file():
        raise SystemExit(f"FAIL: extra2 manifest missing: {extra2_path} — run build_gl_extra2_manifest.py")

    manifest = merge_v10e(
        _load(base_path),
        _load(extra2_path),
        extra2_use_enhanced=args.extra2_enhanced_paths,
        use_v2_cache=args.v2_cache_paths,
    )
    st = manifest["glaucoma_stats"]
    print(
        f"GL base={st['base_gl_count']} +added={st['extra2_added']} "
        f"updated={st['extra2_updated']} → total_gl={st['total_gl']} "
        f"(normal={st['normal']} abnormal={st['abnormal']})"
    )

    out = args.output if args.output.is_absolute() else ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK → {out} total={manifest['total']} coverage={manifest['label_coverage']}")


if __name__ == "__main__":
    main()
