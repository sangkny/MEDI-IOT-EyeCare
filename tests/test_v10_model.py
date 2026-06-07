"""v10 MultiTaskV10Model · V10Loss 단위 테스트."""
from __future__ import annotations

import math

import pytest

pytest.importorskip("torchvision")
import torch

from training.train_v10 import (
    LOSS_WEIGHTS,
    MultiTaskV10Model,
    V10BatchLabels,
    V10Loss,
    _collate_v10,
)

pytestmark = pytest.mark.unit


def test_v10_forward_shapes() -> None:
    model = MultiTaskV10Model(pretrained_imagenet=False)
    x = torch.randn(2, 3, 224, 224)
    out = model.forward(x)
    assert out["dr"].shape == (2, 5)
    assert out["glaucoma"].shape == (2,)
    assert out["amd"].shape == (2,)
    assert out["myopia"].shape == (2,)
    assert out["multidisease"].shape == (2, 28)


def test_v10_loss_masks_missing_labels() -> None:
    criterion = V10Loss()
    outputs = MultiTaskV10Model(pretrained_imagenet=False).forward(torch.randn(2, 3, 224, 224))
    labels = V10BatchLabels(
        dr=torch.tensor([1.0, float("nan")]),
        glaucoma=torch.tensor([float("nan"), float("nan")]),
        amd=torch.tensor([float("nan"), float("nan")]),
        myopia=torch.tensor([float("nan"), float("nan")]),
        multidisease=torch.full((2, 28), float("nan")),
        mask_dr=torch.tensor([True, False]),
        mask_gl=torch.tensor([False, False]),
        mask_amd=torch.tensor([False, False]),
        mask_myo=torch.tensor([False, False]),
        mask_multi=torch.tensor([False, False]),
    )
    loss, parts = criterion(outputs, labels)
    assert loss.item() >= 0.0
    assert "dr" in parts
    assert "glaucoma" not in parts


def test_v10_collate_nan_masks() -> None:
    batch = [
        (torch.zeros(3, 224, 224), {"dr": 2.0, "glaucoma": math.nan, "amd": math.nan, "myopia": math.nan, "multidisease": None}),
        (torch.zeros(3, 224, 224), {"dr": math.nan, "glaucoma": 1.0, "amd": math.nan, "myopia": math.nan, "multidisease": None}),
    ]
    _, labels = _collate_v10(batch)
    assert labels.mask_dr.tolist() == [True, False]
    assert labels.mask_gl.tolist() == [False, True]


def test_loss_weights_sum() -> None:
    assert pytest.approx(sum(LOSS_WEIGHTS.values()), rel=1e-6) == 1.0
