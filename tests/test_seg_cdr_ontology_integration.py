"""
파일명: test_seg_cdr_ontology_integration.py
목적: cdr_from_seg_logits() 출력이 build_glaucoma_ontology_payload()와
      validate_glaucoma_ontology()를 끝까지 통과하는지 검증
      (v12/v13에서 만든 seg 기반 CDR이 향후 운영에 연동될 때
       바로 깨지지 않도록 미리 안전망 마련 — 아직 운영 미연동이지만
       "연동 가능한 상태인지"를 지속 확인)
히스토리:
  2026-06-22 - 최초 작성 (온톨로지 진단 결과 — seg→ontology 갭 해소)
"""
from __future__ import annotations

import logging

import pytest
import torch

from services.cdr_estimator import (
    _category_from_cdr,
    cdr_from_seg_logits,
    estimate_cdr_from_probability,
)
from services.glaucoma_cnn import glaucoma_prediction_from_probability
from services.glaucoma_ontology import (
    build_glaucoma_ontology_payload,
    validate_glaucoma_ontology,
)

pytestmark = pytest.mark.unit
log = logging.getLogger(__name__)


def _make_seg_logits(
    *,
    disc_slice: tuple[int, int, int, int] = (4, 20, 4, 20),
    cup_slice: tuple[int, int, int, int] = (8, 16, 8, 16),
    size: int = 224,
) -> torch.Tensor:
    """더미 seg logits (N,3,H,W) — disc=1, cup=2."""
    logits = torch.zeros(1, 3, size, size)
    y0, y1, x0, x1 = disc_slice
    logits[0, 1, y0:y1, x0:x1] = 5.0
    cy0, cy1, cx0, cx1 = cup_slice
    logits[0, 2, cy0:cy1, cx0:cx1] = 10.0
    return logits


def _cup_disc_ratio_from_seg(logits: torch.Tensor) -> dict:
    val = float(cdr_from_seg_logits(logits)[0].item())
    cat = _category_from_cdr(val)
    return {
        "value": round(val, 3),
        "category": cat,
        "method": "segmentation_based",
    }


@pytest.mark.asyncio
async def test_seg_cdr_through_ontology_payload_and_validate() -> None:
    logits = _make_seg_logits()
    cdr_dict = _cup_disc_ratio_from_seg(logits)
    assert 0.0 <= cdr_dict["value"] <= 1.0

    pred = glaucoma_prediction_from_probability(0.85)
    payload = build_glaucoma_ontology_payload(
        pred,
        model_used="v10c-seg-mock",
        icd10_code="H40.1",
        referral_urgency="immediate",
        cup_disc_ratio=cdr_dict,
    )
    result = await validate_glaucoma_ontology(payload)
    assert result.passed is True
    assert result.error_count == 0


@pytest.mark.asyncio
async def test_glau_sem_005_applies_to_seg_based_cdr() -> None:
    """큰 cup → 높은 CDR인데 risk_level이 LOW면 GLAU-SEM-005 거부."""
    logits = _make_seg_logits(
        disc_slice=(20, 180, 20, 180),
        cup_slice=(30, 170, 30, 170),
    )
    cdr_dict = _cup_disc_ratio_from_seg(logits)
    assert cdr_dict["value"] > 0.75

    pred = glaucoma_prediction_from_probability(0.55)
    assert pred.risk_level == "MODERATE"

    payload = build_glaucoma_ontology_payload(
        pred,
        model_used="v10c-seg-mock",
        icd10_code="H40.1",
        referral_urgency="routine",
        cup_disc_ratio=cdr_dict,
    )
    result = await validate_glaucoma_ontology(payload)
    assert not result.passed
    assert any(e.code == "GLAU-SEM-005" for e in result.errors)


@pytest.mark.asyncio
async def test_seg_vs_probability_cdr_risk_category_comparison(caplog) -> None:
    """동일 probability에서 seg CDR vs probability CDR — 카테고리 비교 로깅."""
    caplog.set_level(logging.INFO)
    prob = 0.72
    pred = glaucoma_prediction_from_probability(prob)

    prob_cdr = estimate_cdr_from_probability(prob)
    seg_logits = _make_seg_logits(
        disc_slice=(30, 190, 30, 190),
        cup_slice=(70, 150, 70, 150),
    )
    seg_cdr_val = float(cdr_from_seg_logits(seg_logits)[0].item())
    seg_cat = _category_from_cdr(seg_cdr_val)
    prob_cat = prob_cdr.cdr_category

    log.info(
        "cdr_compare prob=%.2f prob_cdr=%.3f(%s) seg_cdr=%.3f(%s) risk=%s",
        prob,
        prob_cdr.cdr_value,
        prob_cat,
        seg_cdr_val,
        seg_cat,
        pred.risk_level,
    )

    assert prob_cat in ("normal", "suspect", "glaucoma")
    assert seg_cat in ("normal", "suspect", "glaucoma")
    assert 0.0 <= seg_cdr_val <= 1.0
    assert "cdr_compare" in caplog.text
