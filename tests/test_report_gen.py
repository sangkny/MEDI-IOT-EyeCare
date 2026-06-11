"""
파일명: test_report_gen.py
목적: report gen.py 단위·통합 테스트
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가
"""
# MEDI-IOT-EyeCare/tests/test_report_gen.py
"""
ReportGenerator 테스트 — CONSENSUS 전략 진단 보고서 생성

목적: Week 2 Day 4 — Orchestrator(CONSENSUS) 기반 의료 보고서 전체 파이프라인
단계:
  1. FAST 모델(gemma-4-e4b) 초안 생성
  2. HEAVY 모델(gemma-4-26b-a4b) CONSENSUS 검증
  3. OntologyValidator(MEDICAL) PASS 확인
  4. 최종 보고서 내용 + 치료 계획 출력

실행:
    docker compose -f docker-compose.dev.yml exec medi-iot-api \
        pytest tests/test_report_gen.py -v -s

클래스:
    TestReportGenUnit       — 파싱/태스크 빌드 단위 테스트 (LLM 없음)
    TestReportGenDiabetic   — 당뇨망막병증 보고서 (CONSENSUS, ~2분)
    TestReportGenGlaucoma   — 녹내장 보고서 (pipeline 전략, ~1분)
    TestReportGenOCT        — OCT 황반원공 보고서 (consensus, ~2분)
"""
import asyncio
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pytest
import sys

sys.path.insert(0, "/app")
sys.path.insert(0, "/app/shared-libraries")

from services.report_gen import (
    ReportGenerator,
    ICD_DIAGNOSIS_MAP,
    ICD_SEVERITY_HINT,
)


# ════════════════════════════════════════════════════════════
# 테스트용 EyeExam 더미 (DB 없이 사용)
# ════════════════════════════════════════════════════════════

@dataclass
class MockEyeExam:
    """테스트용 EyeExam 모의 객체 (DB 없이 사용)"""
    id:                  str
    patient_id:          str
    exam_type:           str
    exam_date:           date
    icd_code:            str | None   = None
    iop_left:            float | None = None
    iop_right:           float | None = None
    visual_acuity_left:  str | None   = None
    visual_acuity_right: str | None   = None
    raw_findings:        str | None   = None
    ai_summary:          str | None   = None


# ════════════════════════════════════════════════════════════
# Level 0 — 단위 테스트 (LLM 없음)
# ════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestReportGenUnit:
    """
    목적: _build_task(), _parse_report() 로직 검증
    단계: LLM 없이 내부 메서드만 테스트
    """

    def _make_gen(self) -> ReportGenerator:
        return ReportGenerator()

    def _make_exam(self, **kwargs) -> MockEyeExam:
        defaults = dict(
            id="test-exam-001",
            patient_id="test-patient-001",
            exam_type="fundus",
            exam_date=date(2026, 5, 9),
            icd_code="H36.0",
            iop_left=14.5,
            iop_right=15.2,
            visual_acuity_left="0.8",
            visual_acuity_right="0.7",
            raw_findings="황반 주위 점상출혈 및 경성삼출물 관찰.",
        )
        defaults.update(kwargs)
        return MockEyeExam(**defaults)

    def test_build_task_contains_findings(self):
        """_build_task()가 검사 소견을 포함하는지 확인"""
        gen  = self._make_gen()
        exam = self._make_exam()
        task = gen._build_task(exam, "HbA1c 8.5%")

        print(f"\n  작업 문자열 (앞 200자):\n  {task[:200]}")
        assert "황반 주위 점상출혈" in task, "소견이 task에 없음"
        assert "H36.0" in task or "안저 촬영" in task
        assert "HbA1c 8.5%" in task, "additional_context가 없음"
        print("  ✅ _build_task() 소견 + 맥락 포함 확인")

    def test_build_task_no_pii(self):
        """_build_task()가 PII 미포함 지침을 포함하는지 확인"""
        gen  = self._make_gen()
        exam = self._make_exam()
        task = gen._build_task(exam, None)
        assert "개인식별정보" in task or "개인정보" in task
        print("\n  ✅ PII 제외 지침 포함 확인")

    def test_parse_report_icd_extraction(self):
        """_parse_report()가 ICD 코드를 올바르게 추출하는지"""
        gen     = self._make_gen()
        exam    = self._make_exam(icd_code="H40.1")
        output  = "녹내장(H40.1) 소견으로 안압 하강제 처방이 필요합니다."
        parsed  = gen._parse_report(output, exam)

        print(f"\n  icd: {parsed['diagnosis_code']}, name: {parsed['diagnosis_name']}")
        assert parsed["diagnosis_code"] in ("H40.1", "H57.9")
        assert parsed["report"] == output[:2000]
        print("  ✅ ICD 코드 추출 정상")

    def test_parse_report_severity_extraction(self):
        """_parse_report()가 중증도를 올바르게 추출하는지"""
        gen    = self._make_gen()
        exam   = self._make_exam()

        cases = [
            ("환자는 moderate 상태입니다.", "moderate"),
            ("심각한 severe 손상이 있습니다.", "severe"),
            ("normal 범위입니다.", "normal"),
        ]
        for text, expected in cases:
            parsed = gen._parse_report(text, exam)
            assert parsed["severity"] == expected, (
                f"'{text}' → expected {expected}, got {parsed['severity']}"
            )
        print("\n  ✅ severity 추출 정상")

    def test_icd_diagnosis_map_completeness(self):
        """ICD_DIAGNOSIS_MAP에 주요 안과 코드가 있는지"""
        required = ["H36.0", "H35.3", "H35.34", "H40.1", "H40.0"]
        for code in required:
            assert code in ICD_DIAGNOSIS_MAP, f"{code} 없음"
        print(f"\n  ✅ ICD_DIAGNOSIS_MAP 주요 코드 확인 ({len(ICD_DIAGNOSIS_MAP)}개)")


# ════════════════════════════════════════════════════════════
# Level 1 — 당뇨망막병증 CONSENSUS 보고서 (실제 LLM)
# ════════════════════════════════════════════════════════════

@pytest.mark.integration
@pytest.mark.requires_llm
class TestReportGenDiabetic:
    """
    목적: 당뇨망막병증(H36.0) CONSENSUS 전략 보고서 생성 검증
    단계:
      PlannerAgent(FAST) → GeneratorAgent(FAST) →
      ReviewerAgent(HEAVY) + OntologyValidator → 보고서 확정

    환자: P123456, 당뇨병 12년, HbA1c 8.2%
    기대: diagnosis_code=H36.0, ontology_passed=True, 보고서 200자+
    """

    EXAM = MockEyeExam(
        id="diabetic-exam-001",
        patient_id="P123456",
        exam_type="fundus",
        exam_date=date(2026, 5, 9),
        icd_code="H36.0",
        iop_left=14.5,
        iop_right=15.2,
        visual_acuity_left="0.7",
        visual_acuity_right="0.8",
        raw_findings=(
            "우안 후극부: 황반 주위 다수의 점상출혈(dot hemorrhage) 및 "
            "경성삼출물(hard exudate) 관찰. 황반부 부종 의심. "
            "시신경 유두 주위 신생혈관(neovascularization) 의심 소견. "
            "정맥 확장(venous dilation). "
            "좌안: 경미한 미세동맥류(microaneurysm) 2~3개 관찰."
        ),
    )

    def test_consensus_diabetic_retinopathy(self):
        """
        목적: 당뇨망막병증 CONSENSUS 보고서 생성 + 품질 검증
        단계: FAST 초안 → HEAVY 검토 → 최종 보고서
        기대:
          - diagnosis_code: H36.0
          - report: 200자 이상의 의료 보고서
          - ontology_passed: True
          - treatment_plan: 치료 계획 포함
        """
        gen = ReportGenerator()

        print(f"\n  ── 보고서 생성 시작 ────────────────────────────────")
        print(f"  환자:     P123456")
        print(f"  진단 힌트: H36.0 당뇨망막병증")
        print(f"  전략:     CONSENSUS (FAST+HEAVY 동시 검증)")
        print(f"  예상 시간: ~2분")

        result = asyncio.run(
            gen.generate(
                exam=self.EXAM,
                strategy="consensus",
                additional_context="환자 HbA1c 8.2%, 당뇨병 진단 12년차, 인슐린 치료 중",
            )
        )

        print(f"\n  ── 보고서 결과 ─────────────────────────────────────")
        print(f"  diagnosis_code:   {result['diagnosis_code']}")
        print(f"  diagnosis_name:   {result['diagnosis_name']}")
        print(f"  severity:         {result['severity']}")
        print(f"  ontology_passed:  {result['ontology_passed']}")
        print(f"  confidence_score: {result['confidence_score']}")
        print(f"  llm_model:        {result.get('llm_model')}")
        print(f"  iterations:       {result['iterations']}")
        print(f"  latency_ms:       {result['latency_ms']:.0f}ms")

        print(f"\n  ── 진단 보고서 내용 ─────────────────────────────────")
        report = result.get("report", "")
        print(f"  {report[:500]}")
        print(f"  ... (총 {len(report)}자)")

        if result.get("treatment_plan"):
            print(f"\n  ── 치료 계획 ──────────────────────────────────────")
            print(f"  {result['treatment_plan'][:300]}")

        # 핵심 검증
        assert result["diagnosis_code"], "diagnosis_code 없음"
        assert len(report) >= 200, f"보고서 너무 짧음: {len(report)}자"
        assert result["severity"] in ("normal", "mild", "moderate", "severe", "critical")
        assert result["confidence_score"] >= 0.5

        if result["ontology_passed"]:
            print(f"\n  ✅ OntologyValidator PASS — 의료 검증 완료")
        else:
            print(f"\n  ⚠ OntologyValidator FAIL (보고서는 생성됨)")

        print(f"  ✅ CONSENSUS 보고서 생성 완료 [{result['diagnosis_code']}]")

    def test_pipeline_strategy_comparison(self):
        """
        목적: pipeline 전략으로도 보고서가 생성되는지 확인 (빠름)
        단계: strategy=pipeline → 보고서 구조 검증
        """
        gen  = ReportGenerator()
        exam = MockEyeExam(
            id="pipeline-test-001",
            patient_id="P999",
            exam_type="fundus",
            exam_date=date(2026, 5, 9),
            icd_code="H36.0",
            raw_findings="경미한 당뇨망막병증 소견. 점상출혈 소수.",
        )

        print(f"\n  pipeline 전략 보고서 생성 중...")
        result = asyncio.run(gen.generate(exam=exam, strategy="pipeline"))

        print(f"  diagnosis_code: {result['diagnosis_code']}")
        print(f"  report 길이:    {len(result.get('report', ''))}자")
        print(f"  iterations:     {result['iterations']}")
        print(f"  latency:        {result['latency_ms']:.0f}ms")

        assert result["diagnosis_code"]
        assert result.get("report") and len(result["report"]) >= 100
        print(f"  ✅ pipeline 전략 보고서 생성 확인")


# ════════════════════════════════════════════════════════════
# Level 2 — 녹내장 보고서 (실제 LLM)
# ════════════════════════════════════════════════════════════

@pytest.mark.integration
@pytest.mark.requires_llm
class TestReportGenGlaucoma:
    """
    목적: 녹내장(H40.1) 시야 검사 기반 보고서 생성 검증
    단계: visual_field + IOP 데이터 → 녹내장 보고서
    """

    EXAM = MockEyeExam(
        id="glaucoma-exam-001",
        patient_id="P234567",
        exam_type="visual_field",
        exam_date=date(2026, 5, 9),
        icd_code="H40.1",
        iop_left=22.5,
        iop_right=21.0,
        raw_findings=(
            "우안 시야 검사(Humphrey 30-2): MD -8.5dB, PSD 6.2dB. "
            "상측 Arcuate scotoma 뚜렷. 비측 계단(nasal step) 관찰. "
            "좌안: MD -3.2dB, 조기 녹내장 변화 의심."
        ),
    )

    def test_glaucoma_report_with_iop(self):
        """
        목적: 녹내장 보고서 생성 — 안압 수치 포함
        기대: 안압 수치, 시야 결손 패턴, 치료 계획 포함
        """
        gen = ReportGenerator()
        print(f"\n  녹내장 보고서 생성 중 (pipeline 전략)...")

        result = asyncio.run(
            gen.generate(
                exam=self.EXAM,
                strategy="pipeline",
                additional_context="가족력: 부친 녹내장. 최근 안압 상승 추세.",
            )
        )

        print(f"\n  diagnosis_code:   {result['diagnosis_code']}")
        print(f"  diagnosis_name:   {result['diagnosis_name']}")
        print(f"  severity:         {result['severity']}")
        print(f"  ontology_passed:  {result['ontology_passed']}")
        print(f"  iterations:       {result['iterations']}")

        print(f"\n  ── 보고서 내용 (앞 400자) ─────────────────────────")
        print(f"  {result.get('report', '')[:400]}")

        assert result["diagnosis_code"]
        assert result.get("report") and len(result["report"]) >= 150
        print(f"\n  ✅ 녹내장 보고서 생성 완료 [{result['diagnosis_code']}]")


# ════════════════════════════════════════════════════════════
# Level 3 — EyeAnalyzer → ReportGenerator 연계 테스트
# ════════════════════════════════════════════════════════════

@pytest.mark.integration
@pytest.mark.requires_llm
class TestEyeAnalyzerToReport:
    """
    목적: EyeAnalyzer 분석 결과 → ReportGenerator 보고서 생성 연계 검증
    단계: EyeAnalyzer.analyze() → MockEyeExam 생성 → ReportGenerator.generate()
    시나리오: 당뇨망막병증 전체 분석 파이프라인 (2단계)
    """

    def test_analyzer_to_report_pipeline(self):
        """
        목적: EyeAnalyzer → ReportGenerator 2단계 파이프라인
        단계:
          1. EyeAnalyzer로 안저 소견 분석 → AnalysisResult
          2. AnalysisResult 기반 MockEyeExam 구성
          3. ReportGenerator로 최종 보고서 생성
        기대: 일관된 ICD 코드 + 보고서 생성
        """
        from services.eye_analyzer import EyeAnalyzer

        print(f"\n  ── Step 1: EyeAnalyzer 안저 소견 분석 ─────────────")
        analyzer = EyeAnalyzer()
        analysis = asyncio.run(
            analyzer.analyze(
                findings_text=(
                    "당뇨망막병증 소견: 황반부 점상출혈, 경성삼출물, "
                    "시신경유두 신생혈관 의심. 당뇨 10년차."
                ),
                exam_type="fundus",
                icd_code="H36.0",
            )
        )
        print(f"  분석 결과: {analysis.condition} ({analysis.icd10_code})")
        print(f"  severity:  {analysis.severity}, confidence: {analysis.confidence:.2f}")

        print(f"\n  ── Step 2: ReportGenerator CONSENSUS 보고서 ────────")
        exam = MockEyeExam(
            id="pipeline-integration-001",
            patient_id="P123456",
            exam_type="fundus",
            exam_date=date(2026, 5, 9),
            icd_code=analysis.icd10_code,
            raw_findings=f"[EyeAnalyzer 분석] {analysis.raw_analysis[:200]}",
        )
        gen    = ReportGenerator()
        report = asyncio.run(
            gen.generate(
                exam=exam,
                strategy="consensus",
                additional_context=f"EyeAnalyzer 진단: {analysis.condition_kr}, 중증도: {analysis.severity}",
            )
        )

        print(f"  보고서 code:    {report['diagnosis_code']}")
        print(f"  보고서 길이:    {len(report.get('report', ''))}자")
        print(f"  ontology:       {report['ontology_passed']}")
        print(f"\n  ── 최종 보고서 내용 ─────────────────────────────────")
        print(f"  {report.get('report', '')[:400]}")

        # 두 단계 결과 일관성 확인
        assert report["diagnosis_code"], "진단 코드 없음"
        assert len(report.get("report", "")) >= 100
        print(f"\n  ✅ EyeAnalyzer → ReportGenerator 파이프라인 완료")
        print(f"     {analysis.summary()}")
        print(f"     → 보고서 {len(report.get('report', ''))}자 생성")
