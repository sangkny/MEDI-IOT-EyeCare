#!/usr/bin/env python3
"""IDRiD 세그멘테이션 + DR 등급 멀티태스크 (향후).

데이터: ``data/IDRiD_raw/A. Segmentation/`` — MA, HE, EX, SE, OD

계획:
  - 공유 EfficientNet/RETFound backbone
  - 헤드 1: DR 5-class
  - 헤드 2: 병변 픽셀 세그멘테이션
  - GradCAM++ 히트맵 vs 세그 GT 비교로 설명 검증

현재는 SSOT placeholder — v6_se / v7_retfound 단일태스크 우선.
"""
from __future__ import annotations

raise SystemExit(
    "train_multitask.py is not implemented yet. "
    "Use training/train.py (DR) or training/train_retfound.py (ViT)."
)
