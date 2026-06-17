#!/usr/bin/env python3
"""
파일명: scripts/build_disc_cup_masks.py
목적: G1020 json(disc/cup/discLoc 폴리곤) → 세그멘테이션 마스크(png) 생성
      추가로 ORIGA(Masks_Square 폴더 보유 여부 확인 후 활용)도 통합
실행: Docker 컨테이너 내부에서만
히스토리:
  2026-06-17 - 최초 작성 (v12 Disc/Cup 보조헤드 준비)
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

MASK_BG = 0
MASK_DISC = 1
MASK_CUP = 2
DEFAULT_SIZE = 224


def center_crop_square_2d(mask: np.ndarray) -> np.ndarray:
    """짧은 변 기준 중앙 정사각형 크롭 (단일 채널 마스크)."""
    h, w = mask.shape[:2]
    size = min(h, w)
    y0 = (h - size) // 2
    x0 = (w - size) // 2
    return mask[y0 : y0 + size, x0 : x0 + size].copy()


def _polygons_from_shapes(shapes: list[dict]) -> tuple[list[np.ndarray], list[np.ndarray]]:
    disc_polys: list[np.ndarray] = []
    cup_polys: list[np.ndarray] = []
    for shape in shapes:
        label = str(shape.get("label", "")).lower()
        if label == "discloc":
            continue
        pts = shape.get("points") or []
        if len(pts) < 3:
            continue
        arr = np.array(pts, dtype=np.int32)
        if label == "disc":
            disc_polys.append(arr)
        elif label == "cup":
            cup_polys.append(arr)
    return disc_polys, cup_polys


def mask_from_json(json_path: Path, *, image_size: int = DEFAULT_SIZE) -> np.ndarray | None:
    """G1020 labelme json → 0/1/2 마스크 (CenterCrop + resize)."""
    data = json.loads(json_path.read_text(encoding="utf-8"))
    shapes = data.get("shapes") or []
    disc_polys, cup_polys = _polygons_from_shapes(shapes)
    if not disc_polys and not cup_polys:
        return None

    img_w = int(data.get("imageWidth") or 0)
    img_h = int(data.get("imageHeight") or 0)
    if img_w < 1 or img_h < 1:
        stem = json_path.stem
        for ext in (".jpg", ".jpeg", ".png", ".bmp"):
            img_path = json_path.with_name(stem + ext)
            if img_path.is_file():
                img = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
                if img is not None:
                    img_h, img_w = img.shape[:2]
                    break
        if img_w < 1 or img_h < 1:
            return None

    mask = np.zeros((img_h, img_w), dtype=np.uint8)
    for poly in disc_polys:
        cv2.fillPoly(mask, [poly], MASK_DISC)
    for poly in cup_polys:
        cv2.fillPoly(mask, [poly], MASK_CUP)

    cropped = center_crop_square_2d(mask)
    if image_size > 0 and (cropped.shape[0] != image_size or cropped.shape[1] != image_size):
        cropped = cv2.resize(
            cropped,
            (image_size, image_size),
            interpolation=cv2.INTER_NEAREST,
        )
    return cropped


def build_g1020_masks(
    dataset_root: Path,
    *,
    image_size: int = DEFAULT_SIZE,
    dry_run: bool = False,
) -> dict[str, float | int]:
    json_dir = dataset_root / "Glaucoma_extra2/G1020/G1020/Images"
    out_dir = dataset_root / "disc_cup_masks/G1020"
    if not json_dir.is_dir():
        raise FileNotFoundError(f"G1020 json dir not found: {json_dir}")

    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    json_files = sorted(json_dir.glob("*.json"))
    written = 0
    skipped = 0
    disc_ratios: list[float] = []
    cup_ratios: list[float] = []

    for jp in json_files:
        mask = mask_from_json(jp, image_size=image_size)
        if mask is None:
            skipped += 1
            continue
        total = float(mask.size)
        disc_ratios.append(float(((mask == MASK_DISC) | (mask == MASK_CUP)).sum()) / total)
        cup_ratios.append(float((mask == MASK_CUP).sum()) / total)
        if not dry_run:
            out_path = out_dir / f"{jp.stem}_mask.png"
            cv2.imwrite(str(out_path), mask)
        written += 1

    stats: dict[str, float | int] = {
        "json_total": len(json_files),
        "masks_written": written,
        "skipped": skipped,
        "mean_disc_ratio": float(np.mean(disc_ratios)) if disc_ratios else 0.0,
        "mean_cup_ratio": float(np.mean(cup_ratios)) if cup_ratios else 0.0,
        "out_dir": str(out_dir),
    }
    return stats


def check_origa_masks(dataset_root: Path) -> None:
    origa_dir = dataset_root / "Glaucoma_extra2/G1020/ORIGA/Masks_Square"
    if not origa_dir.is_dir():
        print(f"ORIGA Masks_Square 없음 — 스킵: {origa_dir}")
        return
    samples = sorted(origa_dir.iterdir())[:3]
    print(f"ORIGA Masks_Square 존재 ({len(list(origa_dir.iterdir()))} entries), 샘플:")
    for p in samples:
        print(f"  {p.name}")


def main() -> None:
    p = argparse.ArgumentParser(description="G1020 disc/cup segmentation masks")
    p.add_argument("--dataset-root", type=Path, default=Path("/dataset"))
    p.add_argument("--image-size", type=int, default=DEFAULT_SIZE)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    check_origa_masks(args.dataset_root)
    stats = build_g1020_masks(
        args.dataset_root,
        image_size=args.image_size,
        dry_run=args.dry_run,
    )
    print(
        f"G1020 masks: {stats['masks_written']}/{stats['json_total']} "
        f"(skipped={stats['skipped']})"
    )
    print(
        f"mean disc+cup ratio={stats['mean_disc_ratio']:.4f} "
        f"mean cup ratio={stats['mean_cup_ratio']:.4f}"
    )
    print(f"output → {stats['out_dir']}")


if __name__ == "__main__":
    main()
