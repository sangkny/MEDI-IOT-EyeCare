"""
파일명: test_cdr_estimator.py
목적: CDR (Cup-to-Disc Ratio) 추정 검증
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가


CDR 추정 + GLAU-SEM-005 단위 테스트.
"""
from __future__ import annotations

import asyncio

import pytest

from services.cdr_estimator import (
    CDRResult,
    ProbabilityBasedCDR,
    estimate_cdr_from_probability,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "prob, min_cdr, max_cdr, category",
    [
        (0.2, 0.45, 0.65, "normal"),
        (0.65, 0.65, 0.75, "suspect"),
        (0.85, 0.75, 0.85, "glaucoma"),
    ],
)
def test_probability_to_cdr_mapping(
    prob: float, min_cdr: float, max_cdr: float, category: str
) -> None:
    result = estimate_cdr_from_probability(prob)
    assert isinstance(result, CDRResult)
    assert min_cdr <= result.cdr_value <= max_cdr
    assert result.cdr_category == category
    assert result.estimation_method == "probability_based"
    assert len(result.confidence_interval) == 2
    assert result.confidence_interval[0] <= result.cdr_value <= result.confidence_interval[1]
    assert result.clinical_note


@pytest.mark.asyncio
async def test_probability_based_cdr_async() -> None:
    import numpy as np

    est = ProbabilityBasedCDR()
    result = await est.estimate(np.zeros((224, 224, 3), dtype=np.uint8), 0.85)
    assert 0.75 <= result.cdr_value <= 0.85
    d = result.to_dict()
    assert "value" in d
    assert d["method"] == "probability_based"


def test_glau_sem_005_high_cdr_requires_high_risk() -> None:
    from ontology.base import ValidatorType
    from ontology.validator import OntologyValidator

    validator = OntologyValidator.for_medical()
    bad = {
        "task": "glaucoma",
        "glaucoma_grade": 2,
        "grade_label": "glaucoma",
        "probability": 0.85,
        "risk_level": "MODERATE",
        "referral_urgency": "routine",
        "icd10_code": "H40.1",
        "cup_disc_ratio": {"value": 0.82, "category": "glaucoma"},
    }
    result = asyncio.run(
        validator.validate_partial(bad, [ValidatorType.SEMANTIC])
    )
    assert not result.passed
    assert any(e.code == "GLAU-SEM-005" for e in result.errors)


def test_glau_sem_005_consistent_passes() -> None:
    from ontology.base import ValidatorType
    from ontology.validator import OntologyValidator

    validator = OntologyValidator.for_medical()
    good = {
        "task": "glaucoma",
        "glaucoma_grade": 2,
        "grade_label": "glaucoma",
        "probability": 0.79,
        "risk_level": "HIGH",
        "referral_urgency": "immediate",
        "icd10_code": "H40.1",
        "cup_disc_ratio": {"value": 0.80, "category": "glaucoma"},
    }
    result = asyncio.run(
        validator.validate_partial(good, [ValidatorType.SEMANTIC])
    )
    assert result.passed
