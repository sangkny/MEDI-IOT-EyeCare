"""diagnosis_pipeline — 4-에이전트 분기 단위 테스트"""
from __future__ import annotations

import pytest

from services.diagnosis_pipeline import apply_four_agent_decision


@pytest.mark.asyncio
async def test_legacy_mode_unchanged(monkeypatch):
    monkeypatch.setenv("AGENT_DECISION_MODE", "legacy")
    onto, audit, mode = await apply_four_agent_decision(
        dr_grade=1,
        confidence=0.9,
        icd10_code="H36.0",
        patient_explanation="경증",
        ontology_passed_legacy=True,
        patient_id="P-legacy",
    )
    assert mode == "legacy"
    assert onto is True
    assert audit.get("mode") == "legacy"


@pytest.mark.asyncio
async def test_four_agent_medical_reject(monkeypatch):
    monkeypatch.setenv("AGENT_DECISION_MODE", "four_agent")
    monkeypatch.setenv("AGENT_FOUR_AGENT_MOCK", "1")
    onto, audit, mode = await apply_four_agent_decision(
        dr_grade=2,
        confidence=0.5,
        icd10_code="H35.0",
        patient_explanation="PII 포함 주민번호 노출",
        ontology_passed_legacy=True,
        patient_id="P-pii",
    )
    assert mode == "four_agent"
    assert onto is False
    assert audit.get("mode") == "four_agent"
