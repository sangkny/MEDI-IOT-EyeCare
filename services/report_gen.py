# MEDI-IOT-EyeCare/services/report_gen.py
"""
ReportGenerator — shared-libraries Orchestrator 기반 진단 보고서 생성

핵심 전략: CONSENSUS (FAST + HEAVY 모델 동시 검증)
- PlannerAgent: 진단 작업 계획 수립
- GeneratorAgent: 초안 보고서 생성 (FAST — gemma-4-e4b)
- ReviewerAgent: 의료 정확성 + OntologyValidator 검증 (HEAVY — gemma-4-26b-a4b)
- FixerAgent: 검증 실패 시 수정 (FAST)
- Circuit Breaker: 최대 2회 반복 후 현재 최선 결과 반환
"""
import json
import logging
import re
import time
from typing import Any

from agents.orchestrator import Orchestrator, OrchestraStrategy
from ontology.base import OntologyDomain
from models.medical import EyeExam, ExamTypeEnum

log = logging.getLogger("services.report_gen")

# ICD 코드 → 진단명 매핑 (안과 주요 코드)
ICD_DIAGNOSIS_MAP: dict[str, str] = {
    "H36.0": "당뇨망막병증",
    "H35.3": "황반변성",
    "H35.34": "황반원공",
    "H40.1": "개방각 녹내장",
    "H40.0": "녹내장 의심",
    "H26.0": "피질 백내장",
    "H26.9": "백내장",
    "H18.6": "원추각막",
    "H04.1": "안구건조증",
}

# ICD 코드 → 기본 중증도 힌트
ICD_SEVERITY_HINT: dict[str, str] = {
    "H36.0": "moderate",
    "H35.3": "moderate",
    "H35.34": "severe",
    "H40.1": "moderate",
    "H40.0": "mild",
}


class ReportGenerator:
    """
    진단 보고서 생성기

    shared-libraries Orchestrator를 활용하여
    의료적으로 검증된 안과 진단 보고서를 생성합니다.
    Week 3: RAG(Retrieval-Augmented Generation) 통합으로 정확도 향상
    """

    async def generate(
        self,
        exam: EyeExam,
        strategy: str = "consensus",
        additional_context: str | None = None,
        db=None,                           # RAG 활성화 시 DB 세션 전달
        use_rag: bool = True,              # RAG 컨텍스트 활용 여부
    ) -> dict[str, Any]:
        """
        검사 기록 기반 진단 보고서 생성 (RAG 통합)

        Args:
            exam:               EyeExam 모델 인스턴스
            strategy:           Orchestrator 전략 (consensus 권장)
            additional_context: 추가 임상 맥락
            db:                 RAG 활성화 시 AsyncSession 전달
            use_rag:            RAG 컨텍스트 활용 여부 (기본 True)

        Returns:
            dict: diagnosis_code, diagnosis_name, severity, report,
                  treatment_plan, llm_model, iterations, latency_ms,
                  ontology_passed, confidence_score, rag_used
        """
        t0 = time.monotonic()

        # ── RAG 컨텍스트 조회 (지식베이스에서 관련 문서 검색) ──
        rag_context = ""
        rag_used    = False
        if use_rag and db is not None:
            try:
                from services.knowledge_base import KnowledgeBase
                kb          = KnowledgeBase(db)
                query       = f"{exam.exam_type} {exam.icd_code or ''} {exam.raw_findings or ''}"
                rag_context = await kb.get_rag_context(
                    query=query[:300],
                    top_k=3,
                    icd_code=exam.icd_code,
                )
                rag_used = bool(rag_context)
                if rag_used:
                    log.info(f"[RAG] 컨텍스트 활성화 — {len(rag_context)}자")
            except Exception as e:
                log.warning(f"[RAG] 컨텍스트 조회 실패 (무시): {e}")

        task = self._build_task(exam, additional_context, rag_context)

        log.info(
            f"보고서 생성 시작 | exam={exam.id} | "
            f"type={exam.exam_type} | strategy={strategy}"
        )

        orch = Orchestrator(
            domain=OntologyDomain.MEDICAL,
            strategy=OrchestraStrategy(strategy),
            max_iterations=2,
        )

        result = await orch.execute(task)
        latency_ms = (time.monotonic() - t0) * 1000

        # 결과에서 구조화된 정보 추출
        parsed = self._parse_report(result.output or "", exam)

        parsed.update({
            "llm_model":       self._extract_model(result),
            "iterations":      result.iterations,
            "latency_ms":      latency_ms,
            "ontology_passed": result.passed,
            "confidence_score": 0.85 if result.passed else 0.60,
            "rag_used":        rag_used,
        })

        log.info(
            f"보고서 생성 완료 | ontology={result.passed} | "
            f"iter={result.iterations} | {latency_ms:.0f}ms"
        )
        return parsed

    def _build_task(
        self,
        exam: EyeExam,
        additional_context: str | None,
        rag_context: str = "",
    ) -> str:
        """Orchestrator에 전달할 작업 설명 문자열 생성"""
        exam_type_names = {
            "fundus":       "안저 촬영",
            "oct":          "빛간섭단층촬영(OCT)",
            "visual_field": "시야 검사",
            "slit_lamp":    "세극등 검사",
            "refraction":   "굴절 검사",
            "iop":          "안압 검사",
        }
        exam_name = exam_type_names.get(exam.exam_type, exam.exam_type)

        icd_info = ""
        if exam.icd_code:
            dx_name = ICD_DIAGNOSIS_MAP.get(exam.icd_code, "")
            icd_info = f"관련 진단 코드: {exam.icd_code} ({dx_name})\n"

        iop_info = ""
        if exam.iop_left or exam.iop_right:
            iop_info = (
                f"안압: 좌 {exam.iop_left or 'N/A'} mmHg, "
                f"우 {exam.iop_right or 'N/A'} mmHg\n"
            )

        va_info = ""
        if exam.visual_acuity_left or exam.visual_acuity_right:
            va_info = (
                f"시력: 좌 {exam.visual_acuity_left or 'N/A'}, "
                f"우 {exam.visual_acuity_right or 'N/A'}\n"
            )

        findings = exam.raw_findings or "소견 없음"
        context_block = f"\n추가 임상 정보: {additional_context}" if additional_context else ""

        rag_block = f"\n\n{rag_context}" if rag_context else ""
        return f"""안과 전문의로서 다음 검사 결과에 대한 진단 보고서를 작성하세요.{rag_block}

---

검사 종류: {exam_name}
검사 날짜: {exam.exam_date}
{icd_info}{iop_info}{va_info}
검사 소견:
{findings}{context_block}

다음 항목을 포함하여 의학적으로 정확한 보고서를 작성하세요:
1. 주요 소견 요약
2. 진단 코드(ICD-10)와 진단명
3. 중증도 평가 (normal/mild/moderate/severe/critical)
4. 치료 계획 및 추적 관찰 권고 사항

※ 환자 이름, 주민번호 등 개인식별정보는 절대 포함하지 마세요.
※ 의학적으로 검증된 내용만 기술하세요."""

    def _parse_report(
        self,
        output: str,
        exam: EyeExam,
    ) -> dict[str, Any]:
        """LLM 출력에서 진단 정보 추출"""
        # ICD 코드 추출 시도
        icd_match = re.search(r"\b([A-Z]\d{2}(?:\.\d{1,2})?)\b", output)
        diagnosis_code = (
            icd_match.group(1)
            if icd_match
            else (exam.icd_code or "H57.9")  # 기타 안과 질환
        )

        diagnosis_name = ICD_DIAGNOSIS_MAP.get(
            diagnosis_code,
            "안과 질환 (추가 검토 필요)"
        )

        # 중증도 추출
        severity = ICD_SEVERITY_HINT.get(diagnosis_code, "mild")
        severity_match = re.search(
            r"(normal|mild|moderate|severe|critical)", output, re.IGNORECASE
        )
        if severity_match:
            severity = severity_match.group(1).lower()

        # 치료 계획 추출 (숫자 목록 또는 키워드 이후 텍스트)
        treatment_match = re.search(
            r"(?:치료|처치|권고|추천)[^\n]*\n((?:.+\n?){1,5})",
            output
        )
        treatment_plan = treatment_match.group(1).strip() if treatment_match else None

        return {
            "diagnosis_code": diagnosis_code,
            "diagnosis_name": diagnosis_name,
            "severity": severity,
            "report": output[:2000] if output else "보고서 생성 실패",
            "treatment_plan": treatment_plan,
        }

    def _extract_model(self, result: Any) -> str | None:
        """OrchestratorResult에서 모델명 추출"""
        try:
            if hasattr(result, "lore") and result.lore:
                last = result.lore[-1]
                return getattr(last, "model", None)
        except Exception:
            pass
        return None
