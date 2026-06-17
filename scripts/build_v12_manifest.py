#!/usr/bin/env python3
"""
파일명: scripts/build_v12_manifest.py
목적: unified_v10.json 기반 + disc_cup_mask 경로가 있는 샘플에
      "disc_cup_mask" 필드 추가 → unified_v12.json 생성
      마스크 없는 샘플은 mask=None (학습 시 세그멘테이션 loss 스킵)
히스토리:
  2026-06-17 - 최초 작성
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


def _mask_rel_path(stem: str) -> str:
    return f"disc_cup_masks/G1020/{stem}_mask.png"


def build_v12_manifest(
    *,
    base_manifest: Path,
    dataset_root: Path,
    out_path: Path,
) -> dict[str, int]:
    data = _load_json(base_manifest)
    samples = data.get("samples") or []
    mask_hits = 0
    gl_total = 0
    gl_with_mask = 0

    for entry in samples:
        stem = _image_stem(str(entry.get("path", "")))
        rel = _mask_rel_path(stem)
        mask_path = dataset_root / rel
        if mask_path.is_file():
            entry["disc_cup_mask"] = rel
            mask_hits += 1
        else:
            entry["disc_cup_mask"] = None

        al = entry.get("available_labels") or {}
        if "glaucoma" in al:
            gl_total += 1
            if entry["disc_cup_mask"]:
                gl_with_mask += 1

    out = dict(data)
    out["version"] = "v12"
    out["base_manifest"] = base_manifest.name
    out["seg_mask_note"] = "disc_cup_mask=null → seg loss skip (ignore_index=-1)"
    out["samples"] = samples
    _dump_json(out_path, out)

    return {
        "total": len(samples),
        "mask_hits": mask_hits,
        "gl_total": gl_total,
        "gl_with_mask": gl_with_mask,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="unified_v10 → unified_v12 (+ disc_cup_mask)")
    p.add_argument(
        "--base",
        type=Path,
        default=ROOT / "training/manifests/unified_v10.json",
    )
    p.add_argument(
        "--dataset-root",
        type=Path,
        default=Path("/dataset"),
    )
    p.add_argument(
        "--out",
        type=Path,
        default=ROOT / "training/manifests/unified_v12.json",
    )
    args = p.parse_args()

    base = args.base if args.base.is_absolute() else ROOT / args.base
    out = args.out if args.out.is_absolute() else ROOT / args.out
    stats = build_v12_manifest(
        base_manifest=base,
        dataset_root=args.dataset_root,
        out_path=out,
    )
    print(
        f"v12 manifest → {out}\n"
        f"  samples={stats['total']} mask_hits={stats['mask_hits']}\n"
        f"  GL samples={stats['gl_total']} GL+mask={stats['gl_with_mask']}"
    )


if __name__ == "__main__":
    main()
