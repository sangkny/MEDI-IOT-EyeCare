"""
파일명: test_multitask_model.py
목적: v10c 5-head MultiTaskV10Model — V10BatchLabels, collate, eval
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가


MultiTaskEyeCareModel 단위 테스트.
"""
from __future__ import annotations

import pytest

pytest.importorskip("torchvision")
import torch

from training.train_multitask import MultiTaskEyeCareModel, dr_mse_loss

pytestmark = pytest.mark.unit


def test_multitask_forward_shapes() -> None:
    model = MultiTaskEyeCareModel(pretrained_imagenet=False)
    x = torch.randn(2, 3, 224, 224)
    dr = model.forward_dr(x)
    gl = model.forward_glaucoma(x)
    assert dr.shape == (2, 5)
    assert gl.shape == (2,)


def test_dr_mse_loss() -> None:
    logits = torch.zeros(4, 5)
    logits[:, 2] = 3.0
    y = torch.tensor([2, 2, 3, 1])
    loss = dr_mse_loss(logits, y)
    assert loss.item() >= 0.0
