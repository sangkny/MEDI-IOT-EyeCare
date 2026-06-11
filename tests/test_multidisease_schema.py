"""
파일명: test_multidisease_schema.py
목적: multidisease schema.py 단위·통합 테스트
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가


Phase 4 multidisease schema + manifest constants.
"""
from __future__ import annotations

import pytest

from schemas.integrated_diagnosis import (
    OCTResult,
    ScreeningFinding,
    ScreeningResult,
    SlitLampResult,
)
from training.make_manifest import MULTIDISEASE_TRAIN_CLASSES, RFMID_ALL_DISEASE_COLUMNS


def test_multidisease_train_class_count() -> None:
    assert len(MULTIDISEASE_TRAIN_CLASSES) == 28
    assert "dr" in MULTIDISEASE_TRAIN_CLASSES
    assert "crvo" in MULTIDISEASE_TRAIN_CLASSES
    assert "crao" not in MULTIDISEASE_TRAIN_CLASSES


def test_rfmid_disease_column_count() -> None:
    assert len(RFMID_ALL_DISEASE_COLUMNS) == 45


def test_screening_result_structured_findings() -> None:
    finding = ScreeningFinding(
        disease="crvo",
        probability=0.91,
        risk_level="urgent",
        icd10="H34.8",
    )
    result = ScreeningResult(
        findings=[finding],
        urgent_diseases=["crvo"],
        total_diseases_detected=1,
        recommendations=["즉시 안과 전문의 의뢰"],
        urgent_referral=True,
        referral_urgency="immediate",
        model_used="multidisease_v1(stub)",
    )
    assert result.findings[0].disease == "crvo"
    assert result.total_diseases_detected == 1


def test_slitlamp_oct_stub_models() -> None:
    slit = SlitLampResult(modality="slitlamp", referral_urgency="none")
    oct = OCTResult(modality="oct", macula_metrics={"cmt_um": 0})
    assert slit.modality == "slitlamp"
    assert oct.macula_metrics["cmt_um"] == 0
