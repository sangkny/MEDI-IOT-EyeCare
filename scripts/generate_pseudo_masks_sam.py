#!/usr/bin/env python3
"""
파일명: scripts/generate_pseudo_masks_sam.py
목적: pseudo disc/cup mask 생성 — Phase1(bbox SAM) / Phase2(OSAM DINOv2+SAM)
히스토리:
  2026-06-19 - Phase 1 BBox SAM
  2026-06-19 - Phase 2 OSAM-Fundus (--method osam)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.sam_disc_cup_utils import (
    bbox_from_discloc_json,
    combine_disc_cup_masks,
    cup_box_from_disc_box,
    estimate_disc_bbox,
    resize_mask,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _load_sam_predictor(checkpoint: Path, device: str):
    from segment_anything import SamPredictor, sam_model_registry

    if not checkpoint.is_file():
        raise FileNotFoundError(f"SAM checkpoint missing: {checkpoint}")
    sam = sam_model_registry["vit_b"](checkpoint=str(checkpoint))
    sam.to(device=device)
    return SamPredictor(sam)


def _predict_mask_box(predictor, image_rgb, box):
    import numpy as np

    predictor.set_image(image_rgb)
    masks, scores, _ = predictor.predict(
        box=box.astype(np.float32),
        multimask_output=True,
    )
    return masks[int(np.argmax(scores))]


def sam_disc_cup_mask_bbox(predictor, bgr, disc_box):
    import cv2
    import numpy as np

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    disc_mask = _predict_mask_box(predictor, rgb, disc_box)
    cup_box = cup_box_from_disc_box(disc_box)
    cup_mask = _predict_mask_box(predictor, rgb, cup_box)
    return combine_disc_cup_masks(disc_mask, cup_mask)


def _resolve_image(json_path: Path) -> Path | None:
    for ext in (".jpg", ".jpeg", ".png", ".bmp"):
        p = json_path.with_suffix(ext)
        if p.is_file():
            return p
    return None


def _resolve_manifest_image(entry: dict, data_dir: Path, dr_data_dir: Path | None) -> Path | None:
    rel = str(entry.get("path", "")).replace("\\", "/")
    if rel.startswith("/"):
        return Path(rel)
    if dr_data_dir and ("resized_cache/" in rel or rel.startswith("data/")):
        return dr_data_dir / rel.lstrip("/")
    return data_dir / rel


def _out_subdir(method: str, target: str) -> str:
    if method == "osam":
        return "pseudo_osam/G1020" if target == "g1020" else "pseudo_osam/manifest"
    return "pseudo/G1020" if target == "g1020" else "pseudo/manifest"


def generate_g1020_bbox(
    *,
    dataset_root: Path,
    out_root: Path,
    predictor,
    limit: int,
    image_size: int,
    out_subdir: str,
) -> dict[str, int]:
    json_dir = dataset_root / "Glaucoma_extra2/G1020/G1020/Images"
    out_dir = out_root / out_subdir
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
        mask = sam_disc_cup_mask_bbox(predictor, bgr, box)
        mask = resize_mask(mask, image_size)
        cv2.imwrite(str(out_dir / f"{jp.stem}_mask.png"), mask)
        written += 1
    return {"written": written, "skipped": skipped, "out_dir": str(out_dir)}


def generate_g1020_osam(
    *,
    dataset_root: Path,
    out_root: Path,
    osam,
    limit: int,
    image_size: int,
    out_subdir: str,
) -> dict[str, int]:
    from services.osam_fundus import OSAMFundus

    assert isinstance(osam, OSAMFundus)
    gt_dir = dataset_root / "disc_cup_masks/G1020"
    stems = sorted(p.stem.replace("_mask", "") for p in gt_dir.glob("*_mask.png"))
    if limit > 0:
        stems = stems[:limit]
    out_dir = out_root / out_subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    written = skipped = 0
    refs = osam.load_reference_pool(dataset_root)
    for stem in stems:
        img_path = osam._resolve_g1020_image(stem, dataset_root)
        if img_path is None:
            skipped += 1
            continue
        bgr = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
        if bgr is None:
            skipped += 1
            continue
        pool = [r for r in refs if r.stem != stem]
        if not pool:
            skipped += 1
            continue
        mask = osam.segment_bgr(bgr, pool)
        if mask is None:
            skipped += 1
            continue
        mask = resize_mask(mask, image_size)
        cv2.imwrite(str(out_dir / f"{stem}_mask.png"), mask)
        written += 1
    return {"written": written, "skipped": skipped, "out_dir": str(out_dir)}


def generate_all_gl_osam(
    *,
    manifest_path: Path,
    dataset_root: Path,
    dr_data_dir: Path | None,
    out_root: Path,
    osam,
    limit: int,
    image_size: int,
    skip_existing: bool,
) -> dict[str, int]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    out_dir = out_root / "pseudo_osam/manifest"
    out_dir.mkdir(parents=True, exist_ok=True)
    refs = osam.load_reference_pool(dataset_root)
    written = skipped = missing = 0
    count = 0
    for entry in data.get("samples") or []:
        al = entry.get("available_labels") or {}
        if "glaucoma" not in al:
            continue
        stem = Path(str(entry.get("path", ""))).stem
        out_path = out_dir / f"{stem}_mask.png"
        if skip_existing and out_path.is_file():
            skipped += 1
            continue
        img_path = _resolve_manifest_image(entry, dataset_root, dr_data_dir)
        if img_path is None or not img_path.is_file():
            missing += 1
            continue
        bgr = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
        if bgr is None:
            missing += 1
            continue
        mask = osam.segment_bgr(bgr, refs)
        if mask is None:
            missing += 1
            continue
        cv2.imwrite(str(out_path), resize_mask(mask, image_size))
        written += 1
        count += 1
        if limit > 0 and count >= limit:
            break
    return {"written": written, "skipped": skipped, "missing": missing, "out_dir": str(out_dir)}


def generate_from_manifest_bbox(
    *,
    manifest_path: Path,
    dataset_root: Path,
    dr_data_dir: Path | None,
    out_root: Path,
    predictor,
    limit: int,
    image_size: int,
    skip_existing: bool,
    out_subdir: str,
) -> dict[str, int]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    out_dir = out_root / out_subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    written = skipped = missing = 0
    count = 0
    for entry in data.get("samples") or []:
        al = entry.get("available_labels") or {}
        if "glaucoma" not in al:
            continue
        stem = Path(str(entry.get("path", ""))).stem
        out_path = out_dir / f"{stem}_mask.png"
        if skip_existing and out_path.is_file():
            skipped += 1
            continue
        img_path = _resolve_manifest_image(entry, dataset_root, dr_data_dir)
        if img_path is None or not img_path.is_file():
            missing += 1
            continue
        bgr = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
        if bgr is None:
            missing += 1
            continue
        mask = sam_disc_cup_mask_bbox(predictor, bgr, estimate_disc_bbox(bgr))
        cv2.imwrite(str(out_path), resize_mask(mask, image_size))
        written += 1
        count += 1
        if limit > 0 and count >= limit:
            break
    return {"written": written, "skipped": skipped, "missing": missing, "out_dir": str(out_dir)}


def main() -> None:
    p = argparse.ArgumentParser(description="SAM / OSAM pseudo disc/cup masks")
    p.add_argument("--dataset-root", type=Path, default=Path("/dataset"))
    p.add_argument("--dr-data-dir", type=Path, default=Path("/data_dr"))
    p.add_argument("--checkpoint", type=Path, default=Path("/checkpoints/sam_vit_b_01ec64.pth"))
    p.add_argument("--out-root", type=Path, default=None)
    p.add_argument("--manifest", type=Path, default=ROOT / "training/manifests/unified_v12.json")
    p.add_argument("--method", choices=("bbox", "osam"), default="bbox")
    p.add_argument("--target", choices=("g1020", "all_gl", "eval"), default="g1020")
    p.add_argument("--phase", choices=("g1020", "manifest", "all"), default=None, help="legacy")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--image-size", type=int, default=224)
    p.add_argument("--device", default="cuda")
    p.add_argument("--max-references", type=int, default=80)
    args = p.parse_args()

    if args.phase:
        target = "all_gl" if args.phase in ("manifest", "all") else "g1020"
    else:
        target = args.target

    import torch

    out_root = args.out_root or (args.dataset_root / "disc_cup_masks")
    device = args.device if torch.cuda.is_available() else "cpu"
    print(f"method={args.method} target={target} device={device}")

    predictor = _load_sam_predictor(args.checkpoint, device)
    dr_dir = args.dr_data_dir if args.dr_data_dir.is_dir() else None
    manifest = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest

    if args.method == "osam" and target == "eval":
        from services.osam_fundus import OSAMFundus, eval_leave_one_out

        osam = OSAMFundus(predictor, device=device, max_references=args.max_references)
        stats = eval_leave_one_out(
            osam,
            args.dataset_root,
            limit=args.limit or 10,
            image_size=args.image_size,
        )
        print("OSAM leave-one-out eval:")
        for k, v in stats.items():
            if isinstance(v, float):
                print(f"  {k}: {v:.4f}")
            else:
                print(f"  {k}: {v}")
        if stats.get("n", 0) and stats.get("mean_dice", 0) >= 0.80:
            print("OK: mean Dice >= 0.80 — expand to all_gl")
        elif stats.get("n", 0):
            print("WARN: mean Dice < 0.80 — Plan B/C 검토")
        return

    if args.method == "osam":
        from services.osam_fundus import OSAMFundus

        osam = OSAMFundus(predictor, device=device, max_references=args.max_references)
        if target == "g1020":
            sub = _out_subdir("osam", "g1020")
            stats = generate_g1020_osam(
                dataset_root=args.dataset_root,
                out_root=out_root,
                osam=osam,
                limit=args.limit,
                image_size=args.image_size,
                out_subdir=sub,
            )
            print(f"OSAM G1020: written={stats['written']} skipped={stats['skipped']} → {stats['out_dir']}")
        if target == "all_gl":
            if not manifest.is_file():
                print(f"FAIL: manifest not found: {manifest}")
                return
            stats = generate_all_gl_osam(
                manifest_path=manifest,
                dataset_root=args.dataset_root,
                dr_data_dir=dr_dir,
                out_root=out_root,
                osam=osam,
                limit=args.limit,
                image_size=args.image_size,
                skip_existing=True,
            )
            print(
                f"OSAM all_gl: written={stats['written']} skipped={stats['skipped']} "
                f"missing={stats['missing']} → {stats['out_dir']}"
            )
        return

    sub_g = _out_subdir("bbox", "g1020")
    sub_m = _out_subdir("bbox", "all_gl")
    if target == "g1020":
        stats = generate_g1020_bbox(
            dataset_root=args.dataset_root,
            out_root=out_root,
            predictor=predictor,
            limit=args.limit,
            image_size=args.image_size,
            out_subdir=sub_g,
        )
        print(f"BBox G1020: written={stats['written']} skipped={stats['skipped']} → {stats['out_dir']}")
    if target == "all_gl" and manifest.is_file():
        stats = generate_from_manifest_bbox(
            manifest_path=manifest,
            dataset_root=args.dataset_root,
            dr_data_dir=dr_dir,
            out_root=out_root,
            predictor=predictor,
            limit=args.limit,
            image_size=args.image_size,
            skip_existing=True,
            out_subdir=sub_m,
        )
        print(
            f"BBox all_gl: written={stats['written']} skipped={stats['skipped']} "
            f"missing={stats['missing']} → {stats['out_dir']}"
        )


if __name__ == "__main__":
    main()
