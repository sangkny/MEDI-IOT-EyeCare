"""
파일명: test_fundus_video.py
목적: fundus video.py 단위·통합 테스트
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가


fundus_video — DR 집계·검증 단위 테스트.
"""
from __future__ import annotations

import pytest

from services.fundus_video import aggregate_dr_predictions, validate_fundus_video_upload
from services.retinal_cnn import dr_prediction_from_logits


pytestmark = pytest.mark.unit


def test_aggregate_dr_predictions_picks_worst_grade() -> None:
    p0 = dr_prediction_from_logits([5.0, 0.1, 0.1, 0.1, 0.1])
    p2 = dr_prediction_from_logits([0.1, 0.1, 5.0, 0.1, 0.1])
    agg = aggregate_dr_predictions([p0, p2])
    assert agg.dr_grade == 2


def test_validate_fundus_video_upload_rejects_empty() -> None:
    with pytest.raises(ValueError, match="empty"):
        validate_fundus_video_upload(b"", filename="x.mp4")
