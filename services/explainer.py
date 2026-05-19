"""CNN 분류 + LLM 자연어 설명 통합 (R4-ML+).

흐름:
  1. ``DrPrediction`` (CNN) 파싱
  2. LLM HEAVY — 환자용 설명
  3. LLM FAST — 의사용 임상 요약
  4. ``OntologyValidator.for_medical()`` 검증
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from llm.base import ModelRole
from llm.client import LLMClient
from ontology.base import OntologyDomain
from ontology.validator import OntologyValidator
from services.retinal_cnn import DR_GRADE_CONDITION, DrPrediction

log = logging.getLogger("services.explainer")

DR_GRADE_LABEL_KO = {
    0: "당뇨망막병증 없음",
    1: "경증 당뇨망막병증",
    2: "중등도 당뇨망막병증",
    3: "중증 당뇨망막병증",
    4: "증식성 당뇨망막병증",
}

DR_GRADE_LABEL_EN = {
    0: "No diabetic retinopathy",
    1: "Mild NPDR",
    2: "Moderate NPDR",
    3: "Severe NPDR",
    4: "Proliferative DR",
}

RECOMMENDED_ACTIONS: dict[int, list[str]] = {
    0: ["정기 검진 1년 후", "혈당 관리 유지"],
    1: ["정기 검진 6개월 후", "혈당 HbA1c < 7% 목표"],
    2: ["안과 전문의 3개월 내 방문", "혈압·혈당 조절"],
    3: ["안과 전문의 1개월 내 방문", "레이저 치료 상담"],
    4: ["즉시 안과 방문", "유리체절제술·레이저 상담"],
}

RECOMMENDED_ACTIONS_EN: dict[int, list[str]] = {
    0: ["Annual eye screening", "Maintain glycemic control"],
    1: ["Eye exam in 6 months", "Target HbA1c < 7%"],
    2: ["Ophthalmology visit within 3 months", "BP and glucose control"],
    3: ["Ophthalmology visit within 1 month", "Laser therapy consultation"],
    4: ["Urgent ophthalmology visit", "Vitrectomy/laser consultation"],
}


@dataclass
class DiagnosisExplanation:
    dr_grade: int
    confidence: float
    icd10_code: str
    severity: str
    condition: str
    condition_kr: str
    patient_explanation: str
    clinical_summary: str
    recommended_actions: list[str]
    ontology_passed: bool
    ontology_errors: list[str] = field(default_factory=list)
    model_used: str = "cnn+llm"


class DiagnosisExplainer:
    """CNN 결과 + LLM 설명 통합."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm = llm_client or LLMClient()
        self._validator = OntologyValidator(domain=OntologyDomain.MEDICAL)

    def _get_actions(self, dr_grade: int, lang: str) -> list[str]:
        table = RECOMMENDED_ACTIONS_EN if lang == "en" else RECOMMENDED_ACTIONS
        return list(table.get(dr_grade, table.get(2, [])))

    async def explain(
        self,
        cnn_result: DrPrediction,
        *,
        patient_lang: str = "ko",
        patient_id: str | None = None,
    ) -> DiagnosisExplanation:
        dr_grade = cnn_result.dr_grade
        confidence = cnn_result.confidence
        icd10 = cnn_result.icd10_code
        severity = cnn_result.severity
        cond, cond_kr = DR_GRADE_CONDITION.get(
            dr_grade, ("diabetic_retinopathy", "당뇨망막병증")
        )
        labels = DR_GRADE_LABEL_EN if patient_lang == "en" else DR_GRADE_LABEL_KO
        grade_label = labels.get(dr_grade, str(dr_grade))

        patient_explanation = await self._patient_explanation(
            dr_grade, grade_label, confidence, icd10, patient_lang
        )
        clinical_summary = await self._clinical_summary(
            dr_grade, icd10, severity, cond_kr, confidence
        )
        actions = self._get_actions(dr_grade, patient_lang)

        ont = await self._validate_ontology(
            icd10=icd10,
            condition_kr=cond_kr,
            severity=severity,
            summary=clinical_summary,
            patient_id=patient_id,
        )

        return DiagnosisExplanation(
            dr_grade=dr_grade,
            confidence=confidence,
            icd10_code=icd10,
            severity=severity,
            condition=cond,
            condition_kr=cond_kr,
            patient_explanation=patient_explanation,
            clinical_summary=clinical_summary,
            recommended_actions=actions,
            ontology_passed=ont.passed,
            ontology_errors=[e.message for e in ont.errors[:5]],
        )

    async def _patient_explanation(
        self,
        dr_grade: int,
        grade_label: str,
        confidence: float,
        icd10: str,
        lang: str,
    ) -> str:
        if lang == "en":
            prompt = f"""
Explain diabetic retinopathy stage to a patient in plain English.
Stage: {dr_grade} ({grade_label})
Confidence: {confidence:.0%}
ICD-10: {icd10}

Include:
- What this means in simple terms
- Immediate actions
- Lifestyle advice
- When to return for screening
No personal identifiers. 3-5 short paragraphs.
"""
        else:
            prompt = f"""
당뇨망막병증 {dr_grade}단계({grade_label}) 진단 결과를
환자가 이해할 수 있게 설명해주세요.
신뢰도: {confidence:.0%}
ICD-10: {icd10}

포함 내용:
- 현재 상태 설명 (쉬운 언어)
- 즉시 해야 할 행동
- 생활습관 개선 권고
- 다음 검진 시기
개인식별정보 포함 금지. 3~5문단.
"""
        try:
            resp = await self._llm.chat(prompt.strip(), role=ModelRole.HEAVY)
            return (resp.content or "").strip()
        except Exception as exc:
            log.warning("LLM patient explanation failed: %s", exc)
            return self._template_patient(dr_grade, grade_label, confidence, lang)

    async def _clinical_summary(
        self,
        dr_grade: int,
        icd10: str,
        severity: str,
        condition_kr: str,
        confidence: float,
    ) -> str:
        prompt = (
            f"DR Grade {dr_grade}, ICD-10 {icd10}, severity {severity}, "
            f"diagnosis {condition_kr}, CNN confidence {confidence:.2f}. "
            "Write a 3-sentence clinical summary for an ophthalmologist. Korean."
        )
        try:
            resp = await self._llm.chat(prompt, role=ModelRole.FAST)
            return (resp.content or "").strip()
        except Exception as exc:
            log.warning("LLM clinical summary failed: %s", exc)
            return (
                f"DR grade {dr_grade}, {condition_kr} ({icd10}), "
                f"severity={severity}, CNN confidence={confidence:.2f}."
            )

    def _template_patient(
        self, dr_grade: int, grade_label: str, confidence: float, lang: str
    ) -> str:
        actions = self._get_actions(dr_grade, lang)
        action_text = "; ".join(actions)
        if lang == "en":
            return (
                f"Your screening suggests: {grade_label} (confidence {confidence:.0%}). "
                f"Recommended: {action_text}. Please consult an ophthalmologist for confirmation."
            )
        return (
            f"검사 결과 {grade_label} 가능성이 있습니다(신뢰도 {confidence:.0%}). "
            f"권장 사항: {action_text}. 정확한 진단은 안과 전문의 확인이 필요합니다."
        )

    async def _validate_ontology(
        self,
        *,
        icd10: str,
        condition_kr: str,
        severity: str,
        summary: str,
        patient_id: str | None,
    ):
        from datetime import date

        data = {
            "patient_id": patient_id or "integrated_diagnosis",
            "doctor_id": "medi_integrated_ai",
            "examination_date": str(date.today()),
            "diagnosis_code": icd10,
            "diagnosis_name": condition_kr,
            "severity": severity,
            "findings": summary[:500],
        }
        try:
            return await self._validator.validate(data)
        except Exception as exc:
            log.warning("Ontology validation error: %s", exc)
            from ontology.base import ValidationResult

            return ValidationResult(passed=False, errors=[], warnings=[])


__all__ = ["DiagnosisExplainer", "DiagnosisExplanation", "RECOMMENDED_ACTIONS"]
