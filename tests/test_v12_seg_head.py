"""
파일명: test_v12_seg_head.py
목적: v12 Disc/Cup 세그멘테이션 헤드 단위 테스트
히스토리:
  2026-06-17 - 최초 작성
"""
from __future__ import annotations

import math

import numpy as np
import pytest
import torch

from services.cdr_estimator import cdr_from_disc_cup_mask, cdr_from_seg_logits
from training.train_v10 import (
    MULTI_NUM_CLASSES,
    SEG_IGNORE_INDEX,
    V10BatchLabels,
    V10Dataset,
    V10Loss,
    _collate_v10,
    composite_score,
    MultiTaskV10Model,
)

pytestmark = pytest.mark.unit


def test_mask_load_shape_224(tmp_path) -> None:
    import cv2

    mask_dir = tmp_path / "disc_cup_masks" / "G1020"
    mask_dir.mkdir(parents=True)
    mask_path = mask_dir / "sample_mask.png"
    arr = np.zeros((224, 224), dtype=np.uint8)
    arr[80:140, 80:140] = 1
    arr[100:120, 100:120] = 2
    cv2.imwrite(str(mask_path), arr)

    entries = [
        {
            "path": "dummy/sample.jpg",
            "available_labels": {"glaucoma": 1},
            "disc_cup_mask": "disc_cup_masks/G1020/sample_mask.png",
        }
    ]
    img_path = tmp_path / "dummy"
    img_path.mkdir()
    from PIL import Image

    Image.new("RGB", (224, 224), color=(0, 0, 0)).save(img_path / "sample.jpg")

    ds = V10Dataset(entries, tmp_path, image_size=224, preprocess="none", augment=False)
    _, labels = ds[0]
    mask = labels["disc_cup_mask"]
    assert isinstance(mask, torch.Tensor)
    assert mask.shape == (224, 224)
    assert int(mask[110, 110]) == 2


def test_mask_missing_ignore_index(tmp_path) -> None:
    from PIL import Image

    img_dir = tmp_path / "dummy"
    img_dir.mkdir()
    Image.new("RGB", (224, 224)).save(img_dir / "x.jpg")
    entries = [{"path": "dummy/x.jpg", "available_labels": {"glaucoma": 0}}]
    ds = V10Dataset(entries, tmp_path, image_size=224, preprocess="none")
    _, labels = ds[0]
    mask = labels["disc_cup_mask"]
    assert isinstance(mask, torch.Tensor)
    assert (mask == SEG_IGNORE_INDEX).all()


def test_collate_mask_seg_flag(tmp_path) -> None:
    from PIL import Image

    img_dir = tmp_path / "d"
    img_dir.mkdir()
    Image.new("RGB", (224, 224)).save(img_dir / "a.jpg")
    Image.new("RGB", (224, 224)).save(img_dir / "b.jpg")

    m = torch.zeros(224, 224, dtype=torch.long)
    m[50:80, 50:80] = 1
    batch = [
        (torch.randn(3, 224, 224), {"dr": math.nan, "glaucoma": 1.0, "amd": math.nan, "myopia": math.nan, "multidisease": None, "disc_cup_mask": m}),
        (torch.randn(3, 224, 224), {"dr": math.nan, "glaucoma": 0.0, "amd": math.nan, "myopia": math.nan, "multidisease": None, "disc_cup_mask": torch.full((224, 224), SEG_IGNORE_INDEX, dtype=torch.long)}),
    ]
    _, lb = _collate_v10(batch)
    assert lb.mask_seg is not None
    assert lb.mask_seg[0].item() is True
    assert lb.mask_seg[1].item() is False


def test_seg_head_forward_shape() -> None:
    model = MultiTaskV10Model(pretrained_imagenet=True, seg_head=True, image_size=224)
    x = torch.randn(2, 3, 224, 224)
    out = model.forward(x)
    assert out["seg"].shape == (2, 3, 224, 224)
    assert out["cdr"].shape == (2,)


def test_cdr_from_mask_and_logits() -> None:
    mask = np.zeros((64, 64), dtype=np.uint8)
    mask[10:50, 10:50] = 1
    mask[20:35, 20:35] = 2
    cdr = cdr_from_disc_cup_mask(mask)
    cup_area = float((mask == 2).sum())
    disc_area = float(((mask == 1) | (mask == 2)).sum())
    expected = cup_area / disc_area
    assert 0.0 <= cdr <= 1.0
    assert abs(cdr - expected) < 1e-6

    logits = torch.zeros(1, 3, 32, 32)
    logits[0, 2, 8:16, 8:16] = 10.0
    logits[0, 1, 4:20, 4:20] = 5.0
    cdr_t = cdr_from_seg_logits(logits)
    assert cdr_t.shape == (1,)
    assert 0.0 <= float(cdr_t[0]) <= 1.0


def test_composite_includes_seg_dice() -> None:
    w = {"dr": 0.25, "glaucoma": 0.28, "amd": 0.17, "myopia": 0.17, "multidisease": 0.13}
    base = composite_score(
        qwk=0.9, gl_auc=0.8, amd_auc=0.7, myo_auc=0.6, mauc=0.5,
        loss_weights=w, seg_composite_weight=0.0,
    )
    with_seg = composite_score(
        qwk=0.9, gl_auc=0.8, amd_auc=0.7, myo_auc=0.6, mauc=0.5,
        seg_dice=1.0, loss_weights=w, seg_composite_weight=0.05,
    )
    assert with_seg > base
    assert abs(with_seg - (base * 0.95 + 0.05)) < 1e-6


def test_v10_loss_seg_branch() -> None:
    model = MultiTaskV10Model(pretrained_imagenet=True, seg_head=True, image_size=32)
    criterion = V10Loss(seg_weight=0.05, loss_weights={"dr": 0.25, "glaucoma": 0.28, "amd": 0.17, "myopia": 0.17, "multidisease": 0.13})
    x = torch.randn(2, 3, 32, 32)
    out = model.forward(x)
    masks = torch.full((2, 32, 32), SEG_IGNORE_INDEX, dtype=torch.long)
    masks[0, 5:20, 5:20] = 1
    masks[0, 10:15, 10:15] = 2
    lb = V10BatchLabels(
        dr=torch.tensor([float("nan"), float("nan")]),
        glaucoma=torch.tensor([1.0, 0.0]),
        amd=torch.tensor([float("nan"), float("nan")]),
        myopia=torch.tensor([float("nan"), float("nan")]),
        multidisease=torch.full((2, MULTI_NUM_CLASSES), float("nan")),
        mask_dr=torch.tensor([False, False]),
        mask_gl=torch.tensor([True, True]),
        mask_amd=torch.tensor([False, False]),
        mask_myo=torch.tensor([False, False]),
        mask_multi=torch.tensor([False, False]),
        disc_cup_mask=masks,
        mask_seg=torch.tensor([True, False]),
    )
    loss, parts = criterion(out, lb)
    assert float(loss) >= 0.0
    assert "seg" in parts or "glaucoma" in parts
