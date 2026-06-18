"""v13 SAM pseudo-mask 유틸 단위 테스트 (SAM/GPU 불필요)."""
from __future__ import annotations

import json

import numpy as np
import pytest

from scripts.sam_disc_cup_utils import (
    bbox_from_shapes,
    combine_disc_cup_masks,
    cup_box_from_disc_box,
    estimate_disc_bbox,
    mean_disc_cup_dice,
    resize_mask,
)

pytestmark = pytest.mark.unit


def test_bbox_from_discloc_shapes() -> None:
    shapes = [
        {"label": "discLoc", "points": [[10, 20], [110, 120]]},
    ]
    box = bbox_from_shapes(shapes)
    assert box is not None
    assert np.allclose(box, [10, 20, 110, 120])


def test_estimate_disc_bbox_reasonable() -> None:
    img = np.zeros((512, 512, 3), dtype=np.uint8)
    cv2 = pytest.importorskip("cv2")
    cv2.circle(img, (256, 256), 60, (220, 220, 220), -1)
    box = estimate_disc_bbox(img)
    x1, y1, x2, y2 = box
    assert x2 > x1 and y2 > y1
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    assert 200 < cx < 310
    assert 200 < cy < 310


def test_combine_disc_cup_and_dice() -> None:
    disc = np.zeros((32, 32), dtype=bool)
    cup = np.zeros((32, 32), dtype=bool)
    disc[8:24, 8:24] = True
    cup[14:20, 14:20] = True
    mask = combine_disc_cup_masks(disc, cup)
    assert mask[10, 10] == 1
    assert mask[16, 16] == 2
    dice = mean_disc_cup_dice(mask, mask.copy())
    assert dice == pytest.approx(1.0)


def test_resize_mask_nearest() -> None:
    m = np.zeros((400, 600), dtype=np.uint8)
    m[150:250, 250:350] = 2
    out = resize_mask(m, 224)
    assert out.shape == (224, 224)
    assert out.max() <= 2
