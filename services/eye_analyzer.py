# MEDI-IOT-EyeCare/services/eye_analyzer.py
"""
EyeAnalyzer — 안과 소견 분석 서비스

shared-libraries LLMClient(VISION 모델 = gemma-4-26b-a4b)를 사용하여
안저 촬영, OCT, 시야 검사 소견을 분석하고 구조화된 결과를 반환합니다.

analyze() 통합 메서드:
  - 검사 타입별 프롬프트 선택
  - 결과 파싱: condition, severity, icd10_code, confidence 추출
  - OntologyValidator(MEDICAL) 자동 검증
  - 구조화된 AnalysisResult 반환
"""
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from llm.client import LLMClient
from llm.base import ModelRole
from ontology.base import OntologyDomain, ValidationResult
from ontology.validator import OntologyValidator

log = logging.getLogger("services.eye_analyzer")

# ICD 코드 → condition 이름 매핑
ICD_CONDITION_MAP: dict[str, str] = {
    "H36.0":  "diabetic_retinopathy",
    "H35.3":  "age_related_macular_degeneration",
    "H35.34": "macular_hole",
    "H40.1":  "open_angle_glaucoma",
    "H40.0":  "glaucoma_suspect",
    "H18.6":  "keratoconus",
    "H26.0":  "cortical_cataract",
    "H04.1":  "dry_eye_syndrome",
    "H35.0":  "background_retinopathy",
    "H57.9":  "other_eye_disorder",
}

SEVERITY_KEYWORDS = {
    "정상": "normal",   "normal": "normal",
    "경미": "mild",     "mild":   "mild",    "초기": "mild",
    "중등": "moderate", "moderate": "moderate",
    "심함": "severe",   "심한": "severe",    "severe": "severe",  "말기": "severe",
    "위험": "critical", "critical": "critical",
}


@dataclass
class AnalysisResult:
    """EyeAnalyzer.analyze() 구조화 반환값"""
    condition:    str              # 진단명 (영문 snake_case)
    condition_kr: str              # 진단명 (한국어)
    severity:     str              # normal|mild|moderate|severe|critical
    icd10_code:   str              # ICD-10 코드 (예: H36.0)
    confidence:   float            # 신뢰도 0.0~1.0
    raw_analysis: str              # LLM 원문 분석 결과
    model_used:   str              # 사용된 모델명
    ontology_passed: bool          # OntologyValidator 검증 결과
    ontology_errors: list[str]     # 검증 실패 시 오류 목록
    exam_type:    str = "unknown"  # 검사 종류

    def summary(self) -> str:
        status = "✅" if self.ontology_passed else "⚠"
        return (
            f"{status} [{self.icd10_code}] {self.condition_kr} | "
            f"severity={self.severity} | "
            f"confidence={self.confidence:.2f} | "
            f"ontology={'PASS' if self.ontology_passed else 'FAIL'}"
        )


class EyeAnalyzer:
    """
    안과 소견 분석기 (텍스트 + 구조화 출력)

    VISION 모델(gemma-4-26b-a4b)로 소견을 분석하고
    condition, severity, icd10_code, confidence를 추출합니다.

    Week 3+ : 실제 이미지(base64) 처리 추가 예정
    """

    def __init__(self) -> None:
        self._client    = LLMClient()
        self._validator = OntologyValidator(domain=OntologyDomain.MEDICAL)
        log.info("EyeAnalyzer 초기화 (VISION + OntologyValidator)")

    # ══════════════════════════════════════════════════════
    # 통합 분석 메서드
    # ══════════════════════════════════════════════════════

    async def analyze(
        self,
        findings_text: str,
        exam_type: str = "fundus",
        icd_code: str | None = None,
        iop_left: float | None = None,
        iop_right: float | None = None,
        additional_context: str | None = None,
    ) -> AnalysisResult:
        """
        안과 소견 통합 분석

        Args:
            findings_text:      검사 소견 원문
            exam_type:          fundus|oct|visual_field|slit_lamp|refraction|iop
            icd_code:           힌트 ICD 코드 (없으면 LLM이 추론)
            iop_left/right:     안압 수치 (mmHg)
            additional_context: 추가 임상 정보

        Returns:
            AnalysisResult (condition, severity, icd10_code, confidence, ...)
        """
        log.info(f"[EyeAnalyzer] 분석 시작 — exam_type={exam_type}")

        # 1. 검사 타입에 맞는 분석 실행
        raw = await self._dispatch_analysis(
            findings_text, exam_type, icd_code, iop_left, iop_right, additional_context
        )

        # 2. 구조화 파싱
        parsed = self._parse_analysis(raw, icd_code, exam_type)

        # 3. OntologyValidator 검증
        ont_result = await self._run_ontology_validation(parsed, findings_text)

        result = AnalysisResult(
            condition=parsed["condition"],
            condition_kr=parsed["condition_kr"],
            severity=parsed["severity"],
            icd10_code=parsed["icd10_code"],
            confidence=parsed["confidence"],
            raw_analysis=raw["raw_analysis"],
            model_used=raw.get("model_used", "unknown"),
            ontology_passed=ont_result.passed,
            ontology_errors=[e.message for e in ont_result.errors[:5]],
            exam_type=exam_type,
        )

        log.info(f"[EyeAnalyzer] {result.summary()}")
        return result

    # ══════════════════════════════════════════════════════
    # 검사 타입별 분석
    # ══════════════════════════════════════════════════════

    async def _dispatch_analysis(
        self,
        findings_text: str,
        exam_type: str,
        icd_code: str | None,
        iop_left: float | None,
        iop_right: float | None,
        additional_context: str | None,
    ) -> dict[str, Any]:
        """검사 타입에 맞는 분석 메서드 호출"""
        if exam_type in ("fundus",):
            return await self.analyze_fundus_findings(
                findings_text, icd_code, additional_context
            )
        elif exam_type == "oct":
            return await self.analyze_oct_findings(findings_text, icd_code)
        elif exam_type == "visual_field":
            return await self.analyze_visual_field(
                findings_text, iop_left, iop_right
            )
        else:
            # slit_lamp, refraction, iop 등 범용 분석
            return await self._analyze_general(
                findings_text, exam_type, icd_code, additional_context
            )

    async def analyze_fundus_findings(
        self,
        findings_text: str,
        icd_code: str | None = None,
        additional_context: str | None = None,
    ) -> dict[str, Any]:
        """안저 검사 소견 분석"""
        icd_info     = f" (ICD: {icd_code})" if icd_code else ""
        context_info = f"\n추가 정보: {additional_context}" if additional_context else ""

        prompt = f"""당신은 안과 전문의 AI 어시스턴트입니다.
다음 안저 검사 소견{icd_info}을 분석하고, 반드시 아래 JSON 형식으로 응답하세요.{context_info}

검사 소견:
{findings_text}

응답 형식 (JSON만 출력):
{{
  "condition": "diabetic_retinopathy",
  "condition_kr": "당뇨망막병증",
  "icd10_code": "H36.0",
  "severity": "moderate",
  "confidence": 0.85,
  "key_findings": ["점상출혈", "경성삼출물", "신생혈관 의심"],
  "treatment_recommendation": "즉시 안과 추적 관찰 및 레이저 치료 고려",
  "brief_summary": "비증식성 당뇨망막병증 중등도"
}}

severity 선택: normal|mild|moderate|severe|critical
개인식별정보 포함 금지."""

        response = await self._client.chat(prompt=prompt, role=ModelRole.VISION)
        return {"raw_analysis": response.content, "model_used": response.model_used}

    async def analyze_oct_findings(
        self,
        findings_text: str,
        icd_code: str | None = None,
    ) -> dict[str, Any]:
        """OCT 검사 소견 분석"""
        prompt = f"""안과 전문의 AI로서 다음 OCT 검사 소견을 분석하고 JSON으로 응답하세요.

소견: {findings_text}
힌트 ICD: {icd_code or '미지정'}

응답 형식 (JSON만 출력):
{{
  "condition": "macular_hole",
  "condition_kr": "황반원공",
  "icd10_code": "H35.34",
  "severity": "severe",
  "confidence": 0.90,
  "key_findings": ["황반원공 확인", "층 구조 손상"],
  "treatment_recommendation": "유리체절제술 고려",
  "brief_summary": "황반원공 수술 필요 가능"
}}

severity: normal|mild|moderate|severe|critical
개인정보 포함 금지."""

        response = await self._client.chat(prompt=prompt, role=ModelRole.VISION)
        return {"raw_analysis": response.content, "model_used": response.model_used}

    async def analyze_visual_field(
        self,
        findings_text: str,
        iop_left: float | None = None,
        iop_right: float | None = None,
    ) -> dict[str, Any]:
        """시야 검사 소견 분석"""
        iop_info = ""
        if iop_left or iop_right:
            iop_info = f"\n안압: 좌 {iop_left or 'N/A'} mmHg / 우 {iop_right or 'N/A'} mmHg"

        prompt = f"""안과 전문의 AI로서 다음 시야 검사 결과를 분석하고 JSON으로 응답하세요.{iop_info}

시야 검사 소견: {findings_text}

응답 형식 (JSON만 출력):
{{
  "condition": "open_angle_glaucoma",
  "condition_kr": "개방각 녹내장",
  "icd10_code": "H40.1",
  "severity": "moderate",
  "confidence": 0.80,
  "key_findings": ["Arcuate scotoma", "안압 상승"],
  "treatment_recommendation": "안압 하강제 처방 + 3개월 추적",
  "brief_summary": "중기 녹내장 진행"
}}

severity: normal|mild|moderate|severe|critical
개인정보 포함 금지."""

        response = await self._client.chat(prompt=prompt, role=ModelRole.HEAVY)
        return {"raw_analysis": response.content, "model_used": response.model_used}

    async def _analyze_general(
        self,
        findings_text: str,
        exam_type: str,
        icd_code: str | None,
        additional_context: str | None,
    ) -> dict[str, Any]:
        """범용 안과 검사 분석"""
        prompt = f"""안과 전문의 AI로서 다음 {exam_type} 검사 소견을 분석하고 JSON으로 응답하세요.
{f'ICD 힌트: {icd_code}' if icd_code else ''}
{f'추가 정보: {additional_context}' if additional_context else ''}

소견: {findings_text}

응답 형식 (JSON만 출력):
{{
  "condition": "condition_name",
  "condition_kr": "진단명",
  "icd10_code": "H57.9",
  "severity": "mild",
  "confidence": 0.75,
  "key_findings": ["소견1", "소견2"],
  "treatment_recommendation": "추천 사항",
  "brief_summary": "요약"
}}

개인정보 포함 금지."""

        response = await self._client.chat(prompt=prompt, role=ModelRole.VISION)
        return {"raw_analysis": response.content, "model_used": response.model_used}

    # ══════════════════════════════════════════════════════
    # 결과 파싱
    # ══════════════════════════════════════════════════════

    def _parse_analysis(
        self,
        raw: dict[str, Any],
        hint_icd: str | None,
        exam_type: str,
    ) -> dict[str, Any]:
        """LLM 응답에서 JSON 파싱 → 구조화 딕셔너리"""
        text = raw.get("raw_analysis", "")

        # JSON 블록 추출 시도
        parsed: dict[str, Any] = {}
        json_match = re.search(r"\{[\s\S]*?\}", text)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # ICD 코드
        icd = parsed.get("icd10_code") or hint_icd or ""
        if not icd:
            icd_match = re.search(r"\b([A-Z]\d{2}(?:\.\d{1,2})?)\b", text)
            icd = icd_match.group(1) if icd_match else "H57.9"

        # condition
        condition = parsed.get("condition") or ICD_CONDITION_MAP.get(icd, "eye_disorder")
        condition_kr = parsed.get("condition_kr") or _get_korean_name(icd)

        # severity
        raw_sev = parsed.get("severity", "")
        severity = _normalize_severity(raw_sev, text)

        # confidence
        try:
            confidence = float(parsed.get("confidence", 0.7))
            confidence = max(0.0, min(1.0, confidence))
        except (ValueError, TypeError):
            confidence = 0.7

        return {
            "condition":    condition,
            "condition_kr": condition_kr,
            "icd10_code":   icd,
            "severity":     severity,
            "confidence":   confidence,
        }

    async def _run_ontology_validation(
        self,
        parsed: dict[str, Any],
        findings_text: str,
    ) -> ValidationResult:
        """
        OntologyValidator로 분석 결과 검증

        MEDICAL 도메인 Validator가 요구하는 최소 임상 필드를 포함합니다.
        EyeAnalyzer 컨텍스트에서는 patient_id를 알 수 없으므로
        분석 결과 검증용 placeholder를 사용합니다.
        """
        from datetime import date as _date
        data = {
            "patient_id":       "eye_analyzer_validation",    # placeholder
            "doctor_id":        "eye_analyzer_ai",            # AI 분석자
            "examination_date": str(_date.today()),
            "diagnosis_code":   parsed["icd10_code"],
            "diagnosis_name":   parsed["condition_kr"],
            "severity":         parsed["severity"],
            "findings":         findings_text[:500],
        }
        try:
            return await self._validator.validate(data)
        except Exception as e:
            log.warning(f"OntologyValidator 오류: {e}")
            from ontology.base import ValidationResult as VR
            return VR(passed=False, errors=[], warnings=[])


# ══════════════════════════════════════════════════════════
# 헬퍼 함수
# ══════════════════════════════════════════════════════════

def _get_korean_name(icd: str) -> str:
    mapping = {
        "H36.0":  "당뇨망막병증",
        "H35.3":  "황반변성",
        "H35.34": "황반원공",
        "H40.1":  "개방각 녹내장",
        "H40.0":  "녹내장 의심",
        "H18.6":  "원추각막",
        "H26.0":  "피질 백내장",
        "H04.1":  "안구건조증",
        "H35.0":  "배경 당뇨망막병증",
        "H57.9":  "기타 안과 질환",
    }
    return mapping.get(icd, "안과 질환")


def _normalize_severity(raw: str, text: str) -> str:
    raw_lower = raw.lower()
    if raw_lower in ("normal", "mild", "moderate", "severe", "critical"):
        return raw_lower
    for kr, en in SEVERITY_KEYWORDS.items():
        if kr in text or en in raw_lower:
            return en
    return "mild"
