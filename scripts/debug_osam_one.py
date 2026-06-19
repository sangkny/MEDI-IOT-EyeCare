#!/usr/bin/env python3
"""OSAM 단일 샘플 디버그 — pred/GT 통계 출력."""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.sam_disc_cup_utils import mean_disc_cup_dice, resize_mask
from services.osam_fundus import OSAMFundus


def main() -> None:
    from segment_anything import SamPredictor, sam_model_registry

    dataset_root = Path("/dataset")
    ckpt = Path("/checkpoints/sam_vit_b_01ec64.pth")
    gt_dir = dataset_root / "disc_cup_masks/G1020"
    stem = sorted(p.stem.replace("_mask", "") for p in gt_dir.glob("*_mask.png"))[0]

    sam = sam_model_registry["vit_b"](checkpoint=str(ckpt))
    sam.to(device="cuda")
    predictor = SamPredictor(sam)
    osam = OSAMFundus(predictor, device="cuda", max_references=80)

    gt = cv2.imread(str(gt_dir / f"{stem}_mask.png"), cv2.IMREAD_GRAYSCALE)
    img_path = osam._resolve_g1020_image(stem, dataset_root)
    bgr = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
    print(f"stem={stem} img={bgr.shape} gt_unique={np.unique(gt)}")

    refs = osam.load_reference_pool(dataset_root, exclude_stems={stem})
    pred = osam.segment_bgr(bgr, refs)
    if pred is None:
        print("pred=None")
        return
    print(f"pred_unique={np.unique(pred)} disc_frac={(pred==1).mean():.4f} cup_frac={(pred==2).mean():.4f}")
    pred_224 = resize_mask(pred, 224)
    gt_224 = resize_mask(gt, 224)
    dice = mean_disc_cup_dice(pred_224, gt_224)
    print(f"dice_224={dice:.4f}")


if __name__ == "__main__":
    main()
