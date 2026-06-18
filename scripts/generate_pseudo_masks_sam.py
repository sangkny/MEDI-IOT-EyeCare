#!/usr/bin/env python3
"""
파일명: scripts/generate_pseudo_masks_sam.py
목적: SAM BBox prompt 기반 pseudo disc/cup mask 생성
      G1020 discLoc json → BBox prompt → SAM → disc/cup mask
      GL manifest 샘플 → 자동 BBox 추정 → SAM
히스토리:
  2026-06-19 - 최초 작성 (v13 준비)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.sam_disc_cup_utils import (
    bbox_from_discloc_json,
    combine_disc_cup_masks,
    cup_box_from_disc_box,
    estimate_disc_bbox,
    resize_mask,
)


def _load_sam_predictor(checkpoint: Path, device: str):
    from segment_anything import SamPredictor, sam_model_registry

    if not checkpoint.is_file():
        raise FileNotFoundError(f"SAM checkpoint missing: {checkpoint}")
    sam = sam_model_registry["vit_b"](checkpoint=str(checkpoint))
    sam.to(device=device)
    return SamPredictor(sam)


def _predict_mask(predictor, image_rgb: np.ndarray, box: np.ndarray) -> np.ndarray:
    predictor.set_image(image_rgb)
    masks, scores, _ = predictor.predict(
        box=box.astype(np.float32),
        multimask_output=True,
    )
    return masks[int(np.argmax(scores))]


def sam_disc_cup_mask(predictor, bgr: np.ndarray, disc_box: np.ndarray) -> np.ndarray:
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    disc_mask = _predict_mask(predictor, rgb, disc_box)
    cup_box = cup_box_from_disc_box(disc_box)
    cup_mask = _predict_mask(predictor, rgb, cup_box)
    return combine_disc_cup_masks(disc_mask, cup_mask)


def _resolve_image(json_path: Path) -> Path | None:
    for ext in (".jpg", ".jpeg", ".png", ".bmp"):
        p = json_path.with_suffix(ext)
        if p.is_file():
            return p
    return None


def generate_g1020(
    *,
    dataset_root: Path,
    out_root: Path,
    predictor,
    limit: int = 0,
    image_size: int = 224,
) -> dict[str, int]:
    json_dir = dataset_root / "Glaucoma_extra2/G1020/G1020/Images"
    out_dir = out_root / "pseudo/G1020"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_files = sorted(json_dir.glob("*.json"))
    if limit > 0:
        json_files = json_files[:limit]
    written = skipped = 0
    for jp in json_files:
        img_path = _resolve_image(jp)
        box = bbox_from_discloc_json(jp)
        if img_path is None or box is None:
            skipped += 1
            continue
        bgr = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
        if bgr is None:
            skipped += 1
            continue
        mask = sam_disc_cup_mask(predictor, bgr, box)
        mask = resize_mask(mask, image_size)
        out_path = out_dir / f"{jp.stem}_mask.png"
        cv2.imwrite(str(out_path), mask)
        written += 1
    return {"written": written, "skipped": skipped, "out_dir": str(out_dir)}


def _resolve_manifest_image(entry: dict, data_dir: Path, dr_data_dir: Path | None) -> Path | None:
    rel = str(entry.get("path", "")).replace("\\", "/")
    if rel.startswith("/"):
        return Path(rel)
    if dr_data_dir and ("resized_cache/" in rel or rel.startswith("data/")):
        return dr_data_dir / rel.lstrip("/")
    return data_dir / rel


def generate_from_manifest(
    *,
    manifest_path: Path,
    dataset_root: Path,
    dr_data_dir: Path | None,
    out_root: Path,
    predictor,
    gl_only: bool = True,
    limit: int = 0,
    image_size: int = 224,
    skip_existing: bool = True,
) -> dict[str, int]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    samples = data.get("samples") or []
    out_dir = out_root / "pseudo/manifest"
    out_dir.mkdir(parents=True, exist_ok=True)
    written = skipped = missing = 0
    count = 0
    for entry in samples:
        al = entry.get("available_labels") or {}
        if gl_only and "glaucoma" not in al:
            continue
        if entry.get("disc_cup_mask"):
            rel_gt = str(entry["disc_cup_mask"])
            if "G1020" in rel_gt and (dataset_root / rel_gt).is_file():
                skipped += 1
                continue
        img_path = _resolve_manifest_image(
            entry,
            dataset_root,
            dr_data_dir,
        )
        stem = Path(str(entry.get("path", ""))).stem
        out_path = out_dir / f"{stem}_mask.png"
        if skip_existing and out_path.is_file():
            skipped += 1
            continue
        if img_path is None or not img_path.is_file():
            missing += 1
            continue
        bgr = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
        if bgr is None:
            missing += 1
            continue
        box = estimate_disc_bbox(bgr)
        mask = sam_disc_cup_mask(predictor, bgr, box)
        mask = resize_mask(mask, image_size)
        cv2.imwrite(str(out_path), mask)
        written += 1
        count += 1
        if limit > 0 and count >= limit:
            break
    return {
        "written": written,
        "skipped": skipped,
        "missing": missing,
        "out_dir": str(out_dir),
    }


def main() -> None:
    p = argparse.ArgumentParser(description="SAM pseudo disc/cup masks")
    p.add_argument("--dataset-root", type=Path, default=Path("/dataset"))
    p.add_argument("--dr-data-dir", type=Path, default=Path("/data_dr"))
    p.add_argument("--checkpoint", type=Path, default=Path("/checkpoints/sam_vit_b_01ec64.pth"))
    p.add_argument("--out-root", type=Path, default=None, help="default: dataset-root/disc_cup_masks")
    p.add_argument("--manifest", type=Path, default=ROOT / "training/manifests/unified_v12.json")
    p.add_argument("--phase", choices=("g1020", "manifest", "all"), default="all")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--image-size", type=int, default=224)
    p.add_argument("--device", default="cuda")
    args = p.parse_args()

    out_root = args.out_root or (args.dataset_root / "disc_cup_masks")
    import torch

    device = args.device if torch.cuda.is_available() else "cpu"
    print(f"SAM device={device} checkpoint={args.checkpoint}")
    predictor = _load_sam_predictor(args.checkpoint, device)

    dr_dir = args.dr_data_dir if args.dr_data_dir.is_dir() else None
    manifest = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest

    if args.phase in ("g1020", "all"):
        stats = generate_g1020(
            dataset_root=args.dataset_root,
            out_root=out_root,
            predictor=predictor,
            limit=args.limit,
            image_size=args.image_size,
        )
        print(f"G1020 pseudo: written={stats['written']} skipped={stats['skipped']} → {stats['out_dir']}")

    if args.phase in ("manifest", "all"):
        if not manifest.is_file():
            print(f"WARN: manifest not found: {manifest}")
        else:
            stats = generate_from_manifest(
                manifest_path=manifest,
                dataset_root=args.dataset_root,
                dr_data_dir=dr_dir,
                out_root=out_root,
                predictor=predictor,
                gl_only=True,
                limit=args.limit,
                image_size=args.image_size,
            )
            print(
                f"manifest GL pseudo: written={stats['written']} skipped={stats['skipped']} "
                f"missing={stats['missing']} → {stats['out_dir']}"
            )


if __name__ == "__main__":
    main()
