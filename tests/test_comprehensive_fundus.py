"""Comprehensive DR+Glaucoma 스키마·overall_assessment 단위 테스트."""
from __future__ import annotations

import pytest

from schemas.integrated_diagnosis import (
    AMDResult,
    DRComprehensiveSummary,
    GlaucomaResult,
)
from services.comprehensive_fundus import _build_overall_assessment

pytestmark = pytest.mark.unit


def test_overall_assessment_glaucoma_primary() -> None:
    dr = DRComprehensiveSummary(
        grade=0,
        confidence=0.77,
        icd10_code="H40.0",
        severity="normal",
        ontology_passed=True,
    )
    from schemas.integrated_diagnosis import CupDiscRatioDetail

    glu = GlaucomaResult(
        glaucoma_grade=2,
        grade_label="glaucoma",
        label="glaucoma",
        probability=0.79,
        risk_level="HIGH",
        confidence=0.79,
        cup_disc_ratio=CupDiscRatioDetail(
            value=0.745,
            category="suspect",
            method="probability_based",
            confidence_interval=[0.71, 0.78],
            clinical_note="test",
        ),
        referral_urgency="immediate",
        ontology_passed=True,
        decision="REVISE",
    )
    overall = _build_overall_assessment(dr, glu, lang="ko")
    assert overall.primary_concern == "glaucoma"
    assert overall.referral_urgency == "immediate"
    assert len(overall.findings) >= 2
    assert "녹내장" in overall.findings[1]


def test_dr_summary_grade_field() -> None:
    s = DRComprehensiveSummary(
        grade=2,
        confidence=0.85,
        icd10_code="H36.0",
        severity="moderate",
    )
    d = s.model_dump(by_alias=False)
    assert d["grade"] == 2
    assert "dr_grade" not in d or d.get("grade") == 2


def test_dr_summary_from_explain_revise_fallback() -> None:
    from services.comprehensive_fundus import _dr_summary_from_explain

    summary = _dr_summary_from_explain(
        {
            "dr_grade": 1,
            "confidence": 0.390,
            "icd10_code": "H36.0",
            "severity": "mild",
            "audit_trail": {"decision": "REVISE", "mode": "gate"},
        }
    )
    assert summary.decision == "REVISE"
    assert summary.grade == 1


def test_dr_summary_from_explain_none_becomes_revise() -> None:
    from services.comprehensive_fundus import _dr_summary_from_explain

    summary = _dr_summary_from_explain(
        {
            "dr_grade": 1,
            "confidence": 0.390,
            "icd10_code": "H36.0",
            "severity": "mild",
            "audit_trail": {},
        }
    )
    assert summary.decision == "REVISE"


def test_overall_assessment_amd_primary() -> None:
    dr = DRComprehensiveSummary(
        grade=0,
        confidence=0.77,
        icd10_code="H35.0",
        severity="normal",
        ontology_passed=True,
    )
    amd = AMDResult(
        amd_grade=3,
        grade_label="advanced",
        label="amd",
        probability=0.91,
        risk_level="HIGH",
        confidence=0.91,
        drusen_type="hard",
        vision_impact="severe",
        icd10_code="H35.32",
        referral_urgency="immediate",
        ontology_passed=True,
        decision="APPROVE",
    )
    overall = _build_overall_assessment(dr, None, amd, lang="ko")
    assert overall.primary_concern == "amd"
    assert overall.referral_urgency == "immediate"
    assert any("황반변성" in f for f in overall.findings)


def test_overall_assessment_screening_primary_label() -> None:
    from schemas.integrated_diagnosis import ScreeningFinding, ScreeningResult

    dr = DRComprehensiveSummary(
        grade=0,
        confidence=0.77,
        icd10_code="H40.0",
        severity="normal",
        ontology_passed=True,
    )
    screening = ScreeningResult(
        findings=[
            ScreeningFinding(
                disease="odc",
                korean_name="시신경유두함몰",
                probability=0.82,
                risk_level="urgent",
                icd10="H47.1",
            )
        ],
        urgent_diseases=["odc"],
        total_diseases_detected=1,
        referral_urgency="immediate",
        normal=False,
        top_findings=[
            ScreeningFinding(
                disease="odc",
                korean_name="시신경유두함몰",
                probability=0.82,
                risk_level="urgent",
                icd10="H47.1",
            )
        ],
    )
    overall = _build_overall_assessment(dr, None, None, None, screening, lang="ko")
    assert overall.primary_concern == "odc (시신경유두함몰)"
    assert "disease_" not in overall.primary_concern


def test_overall_assessment_compound_primary() -> None:
    from schemas.integrated_diagnosis import CupDiscRatioDetail, ScreeningFinding, ScreeningResult

    dr = DRComprehensiveSummary(
        grade=0,
        confidence=0.77,
        icd10_code="H40.0",
        severity="normal",
        ontology_passed=True,
    )
    glu = GlaucomaResult(
        glaucoma_grade=2,
        grade_label="glaucoma",
        label="glaucoma",
        probability=0.79,
        risk_level="HIGH",
        confidence=0.79,
        cup_disc_ratio=CupDiscRatioDetail(
            value=0.745,
            category="suspect",
            method="probability_based",
            confidence_interval=[0.71, 0.78],
            clinical_note="test",
        ),
        referral_urgency="immediate",
        ontology_passed=True,
        decision="APPROVE",
    )
    screening = ScreeningResult(
        findings=[
            ScreeningFinding(
                disease="odc",
                korean_name="시신경유두함몰",
                probability=0.78,
                risk_level="urgent",
                icd10="H47.1",
            )
        ],
        urgent_diseases=["odc"],
        total_diseases_detected=1,
        referral_urgency="immediate",
        normal=False,
        top_findings=[
            ScreeningFinding(
                disease="odc",
                korean_name="시신경유두함몰",
                probability=0.78,
                risk_level="urgent",
                icd10="H47.1",
            )
        ],
    )
    overall = _build_overall_assessment(dr, glu, None, None, screening, lang="ko")
    assert overall.primary_concern == "glaucoma + odc"
