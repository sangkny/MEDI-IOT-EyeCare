"""
파일명: test_diagnosis_pipeline.py
목적: DR DecisionGate — REVISE/REJECT/APPROVE 분기 (confidence threshold)
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가


DR DecisionGate 단위 테스트.
"""
from __future__ import annotations

import pytest

from services.diagnosis_pipeline import apply_four_agent_decision

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_dr_gate_revise_below_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    """confidence 0.390 < 0.80 → REVISE (None 금지)."""
    monkeypatch.setenv("MEDI_CNN_DECISION_MIN_CONF", "0.80")
    monkeypatch.setenv("MEDI_CNN_DECISION_REJECT_MAX", "0.50")

    onto, audit, mode = await apply_four_agent_decision(
        dr_grade=1,
        confidence=0.390,
        icd10_code="H36.0",
        patient_explanation="test",
        ontology_passed_legacy=True,
        patient_id="test-patient",
    )

    assert audit["decision"] == "REVISE"
    assert mode == "gate"
    assert onto is True
    assert audit.get("reason") == "below_gate_min"


@pytest.mark.asyncio
async def test_dr_gate_reject_very_low_confidence_normal(monkeypatch: pytest.MonkeyPatch) -> None:
    """grade=0 + confidence < 0.50 → REJECT."""
    monkeypatch.setenv("MEDI_CNN_DECISION_MIN_CONF", "0.80")
    monkeypatch.setenv("MEDI_CNN_DECISION_REJECT_MAX", "0.50")

    onto, audit, mode = await apply_four_agent_decision(
        dr_grade=0,
        confidence=0.35,
        icd10_code="H35.0",
        patient_explanation="test",
        ontology_passed_legacy=True,
        patient_id="test-patient",
    )

    assert audit["decision"] == "REJECT"
    assert mode == "gate"
    assert onto is False


@pytest.mark.asyncio
async def test_dr_gate_approve_legacy_high_confidence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDI_CNN_DECISION_MIN_CONF", "0.80")
    monkeypatch.setenv("MEDI_CNN_DECISION_REJECT_MAX", "0.50")

    import services.diagnosis_pipeline as dp

    monkeypatch.setattr(dp, "_pipeline", (type("F", (), {"is_four_agent_enabled": staticmethod(lambda _r: False)})(), object))

    onto, audit, mode = await apply_four_agent_decision(
        dr_grade=1,
        confidence=0.85,
        icd10_code="H36.0",
        patient_explanation="test",
        ontology_passed_legacy=True,
        patient_id="test-patient",
    )

    assert audit["decision"] == "APPROVE"
    assert mode == "legacy"
    assert onto is True
