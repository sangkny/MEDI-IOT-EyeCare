"""v13 Plan B manifest / ORIGA mask 유틸 테스트."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from scripts.build_disc_cup_masks import center_crop_square_2d
from scripts.build_v13_manifest import build_v13_manifest

pytestmark = pytest.mark.unit


def test_center_crop_square_preserves_classes() -> None:
    m = np.zeros((512, 640), dtype=np.uint8)
    m[200:300, 270:370] = 2
    out = center_crop_square_2d(m)
    assert out.shape == (512, 512)
    assert out.max() == 2


def test_build_v13_plan_b_manifest(tmp_path: Path) -> None:
    ds = tmp_path / "dataset"
    (ds / "disc_cup_masks/G1020").mkdir(parents=True)
    (ds / "disc_cup_masks/ORIGA").mkdir(parents=True)
    cv2 = pytest.importorskip("cv2")
    cv2.imwrite(str(ds / "disc_cup_masks/G1020/img_a_mask.png"), np.ones((224, 224), dtype=np.uint8))
    cv2.imwrite(str(ds / "disc_cup_masks/ORIGA/360_mask.png"), np.full((224, 224), 2, dtype=np.uint8))

    base = tmp_path / "base.json"
    base.write_text(
        json.dumps(
            {
                "samples": [
                    {"path": "x/G1020/img_a.jpg", "available_labels": {"glaucoma": 1}},
                    {"path": "x/ORIGA/360.jpg", "available_labels": {"glaucoma": 0}},
                    {"path": "x/other/nomask.jpg", "available_labels": {"glaucoma": 1}},
                ]
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "v13.json"
    stats = build_v13_manifest(
        base_manifest=base,
        dataset_root=ds,
        out_path=out,
        plan_b=True,
    )
    assert stats["mask_hits"] == 2
    assert stats["g1020_hits"] == 1
    assert stats["origa_hits"] == 1
    assert stats["gl_with_mask"] == 2
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["plan_b"] is True
