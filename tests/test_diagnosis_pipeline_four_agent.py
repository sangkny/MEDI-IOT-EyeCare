"""
파일명: test_diagnosis_pipeline_four_agent.py
목적: 4-에이전트 진단 파이프라인 (Generator→Advocate→Critic→DecisionGate) APPROVE/REVISE/REJECT 검증
히스토리:
  2026-06-11 - gate/four_agent 분리: mock unit + PII REVISE(softened) 기대값 수정
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가
"""
from __future__ import annotations

import pytest

from services.diagnosis_pipeline import apply_four_agent_decision

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_legacy_mode_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
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
async def test_four_agent_medical_pii_revise_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    """confidence ≥ gate_min → four_agent; PII mock → REVISE (REJECT softened)."""
    monkeypatch.setenv("AGENT_DECISION_MODE", "four_agent")
    monkeypatch.setenv("AGENT_FOUR_AGENT_MOCK", "1")
    monkeypatch.setenv("MEDI_CNN_DECISION_MIN_CONF", "0.80")
    onto, audit, mode = await apply_four_agent_decision(
        dr_grade=2,
        confidence=0.85,
        icd10_code="H35.0",
        patient_explanation="PII 포함 주민번호 노출",
        ontology_passed_legacy=True,
        patient_id="P-pii",
    )
    assert mode == "four_agent"
    assert audit.get("mode") == "four_agent"
    assert audit.get("decision") == "REVISE"
    assert audit.get("decision_softened") is True
    assert onto is True
    assert any("PII" in str(i) for i in (audit.get("ontology_issues") or []))


@pytest.mark.slow
@pytest.mark.requires_llm
@pytest.mark.asyncio
async def test_four_agent_medical_reject_live(monkeypatch: pytest.MonkeyPatch) -> None:
    """실 LM Studio four_agent — PII/ontology REJECT 경로 (로컬 전용)."""
    monkeypatch.setenv("AGENT_DECISION_MODE", "four_agent")
    monkeypatch.delenv("AGENT_FOUR_AGENT_MOCK", raising=False)
    monkeypatch.setenv("MEDI_CNN_DECISION_MIN_CONF", "0.80")
    onto, audit, mode = await apply_four_agent_decision(
        dr_grade=2,
        confidence=0.85,
        icd10_code="H35.0",
        patient_explanation="PII 포함 주민번호 노출",
        ontology_passed_legacy=True,
        patient_id="P-pii-live",
    )
    assert mode in {"four_agent", "legacy"}
    assert audit.get("decision") in {"REJECT", "REVISE"}
