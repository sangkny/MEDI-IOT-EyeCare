"""
파일명: test_glaucoma_train.py
목적: glaucoma train.py 단위·통합 테스트
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가


Glaucoma 단독 모델 · Focal Loss smoke.
"""
from __future__ import annotations

import pytest

pytest.importorskip("torchvision")
import torch

from training.train_glaucoma import FocalLoss, GlaucomaClassifier

pytestmark = pytest.mark.unit


def test_glaucoma_classifier_forward() -> None:
    model = GlaucomaClassifier(pretrained_imagenet=False)
    x = torch.randn(2, 3, 224, 224)
    out = model(x)
    assert out.shape == (2,)


def test_focal_loss_positive() -> None:
    crit = FocalLoss(alpha=0.75, gamma=2.0)
    logits = torch.tensor([2.0, -2.0])
    targets = torch.tensor([1.0, 0.0])
    loss = crit(logits, targets)
    assert loss.item() > 0.0
