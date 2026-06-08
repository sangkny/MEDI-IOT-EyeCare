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
    eval_multidisease_mauc,
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


def test_v10_dataset_resolve_dr_absolute_path(tmp_path) -> None:
    from pathlib import Path

    from training.train_v10 import V10Dataset

    ds = V10Dataset([], tmp_path, dr_data_dir=Path("/data_dr"))
    assert ds._resolve_image_path("/data_dr/resized_cache/aptos2019_raw/train_images/x.jpg") == Path(
        "/data_dr/resized_cache/aptos2019_raw/train_images/x.jpg"
    )
    assert ds._resolve_image_path("resized_cache/Messidor-2_raw/IMAGES/y.jpg") == Path(
        "/data_dr/resized_cache/Messidor-2_raw/IMAGES/y.jpg"
    )
    assert ds._resolve_image_path("Glaucoma_raw/foo.jpg") == tmp_path / "Glaucoma_raw/foo.jpg"


def test_normalize_dr_path() -> None:
    from training.build_v10_manifest import normalize_dr_path

    assert normalize_dr_path("aptos2019_raw/train_images/a.jpg") == (
        "/data_dr/resized_cache/aptos2019_raw/train_images/a.jpg"
    )
    assert normalize_dr_path("/data_dr/resized_cache/x.jpg") == "/data_dr/resized_cache/x.jpg"


def test_eval_multidisease_mauc_with_v10_batch_labels() -> None:
    pytest.importorskip("sklearn")
    model = MultiTaskV10Model(pretrained_imagenet=False)
    x = torch.randn(4, 3, 224, 224)
    multi = torch.zeros(4, 28)
    multi[:, 0] = 1.0
    multi[1, 0] = 0.0
    multi[2, 1] = 1.0
    multi[3, 1] = 0.0
    labels = V10BatchLabels(
        dr=torch.full((4,), float("nan")),
        glaucoma=torch.full((4,), float("nan")),
        amd=torch.full((4,), float("nan")),
        myopia=torch.full((4,), float("nan")),
        multidisease=multi,
        mask_dr=torch.zeros(4, dtype=torch.bool),
        mask_gl=torch.zeros(4, dtype=torch.bool),
        mask_amd=torch.zeros(4, dtype=torch.bool),
        mask_myo=torch.zeros(4, dtype=torch.bool),
        mask_multi=torch.ones(4, dtype=torch.bool),
    )

    class _Loader:
        def __iter__(self):
            yield x, labels

    mauc = eval_multidisease_mauc(model, _Loader(), torch.device("cpu"))
    assert 0.0 <= mauc <= 1.0
