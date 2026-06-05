"""Glaucoma four-agent critic fallback · 가중치 단위 테스트."""
from __future__ import annotations

import pytest

from agents.four_agent_types import AdvocateReport, CriticReport
from ontology.validator import OntologyValidator

pytestmark = pytest.mark.unit


def test_glaucoma_mediation_weights_and_critic_fallback() -> None:
    validator = OntologyValidator.for_medical()
    advocate = AdvocateReport(confidence=0.85, summary="ok")
    critic = CriticReport(risk_score=1.0, summary="")
    artifact = {"task": "glaucoma", "probability": 0.79, "confidence": 0.79}

    m = validator.mediate(advocate, critic, "medical", artifact)

    assert m.weights == {"advocate": 0.5, "critic": 0.5}
    assert m.critic_score >= 0.5
    assert m.final_score >= 0.65


def test_glaucoma_mediation_approve_threshold() -> None:
    validator = OntologyValidator.for_medical()
    advocate = AdvocateReport(confidence=0.85, summary="ok")
    critic = CriticReport(risk_score=0.3, summary="ok")
    artifact = {"task": "glaucoma", "probability": 0.79}

    m = validator.mediate(advocate, critic, "medical", artifact)

    assert m.final_score >= 0.65
    assert m.advocate_score == pytest.approx(0.85)
    assert m.critic_score == pytest.approx(0.7)


def test_critic_extreme_risk_neutralized() -> None:
    validator = OntologyValidator.for_medical()
    advocate = AdvocateReport(confidence=0.80, summary="ok")
    critic = CriticReport(risk_score=0.99, summary="")
    artifact = {"task": "glaucoma", "probability": 0.75}

    m = validator.mediate(advocate, critic, "medical", artifact)

    assert m.critic_score >= 0.5
    assert m.final_score >= 0.65
