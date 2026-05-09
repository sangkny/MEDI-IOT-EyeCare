# MEDI-IOT-EyeCare/services/eye_analyzer.py
"""
EyeAnalyzer — 안과 이미지 분석 서비스

shared-libraries LLMClient(VISION 모델 = gemma-4-26b-a4b)를 사용하여
안저 사진, OCT 이미지 등을 분석합니다.

현재 구현: 텍스트 기반 분석 (이미지 → base64 인코딩 후 VISION 모델 전달)
Week 3+ : 실제 이미지 파일 처리 추가 예정
"""
import base64
import logging
from pathlib import Path

from llm.client import LLMClient
from llm.base import ModelRole

log = logging.getLogger("services.eye_analyzer")


class EyeAnalyzer:
    """
    안과 이미지/데이터 분석기

    VISION 모델(gemma-4-26b-a4b)을 사용하여:
    1. 안저 사진 소견 분석
    2. OCT 이미지 층 구조 분석
    3. 시야 검사 결과 해석
    """

    def __init__(self) -> None:
        self._client = LLMClient()
        log.info("EyeAnalyzer 초기화")

    async def analyze_fundus_findings(
        self,
        findings_text: str,
        icd_code: str | None = None,
        additional_context: str | None = None,
    ) -> dict:
        """
        안저 검사 소견 텍스트 분석

        Args:
            findings_text: 의사가 입력한 안저 소견 원문
            icd_code: 관련 ICD-10 코드 (예: H36.0)
            additional_context: 추가 임상 정보

        Returns:
            dict with keys: summary, severity_hint, key_findings, recommendations
        """
        icd_info = f" (ICD: {icd_code})" if icd_code else ""
        context_block = f"\n추가 정보: {additional_context}" if additional_context else ""

        prompt = f"""당신은 안과 전문의 AI 어시스턴트입니다.
다음 안저 검사 소견{icd_info}을 분석해 주세요.{context_block}

검사 소견:
{findings_text}

다음 형식으로 분석해 주세요:
1. 핵심 소견 요약 (2-3문장)
2. 중증도 판단 (normal/mild/moderate/severe/critical)
3. 주요 이상 소견 목록
4. 추천 추가 검사 또는 처치

개인식별정보는 포함하지 마세요."""

        response = await self._client.chat(
            messages=[{"role": "user", "content": prompt}],
            role=ModelRole.VISION,
        )

        return {
            "raw_analysis": response.content,
            "icd_code": icd_code,
            "model_used": response.model,
        }

    async def analyze_oct_findings(
        self,
        findings_text: str,
        icd_code: str | None = None,
    ) -> dict:
        """OCT 검사 소견 분석"""
        prompt = f"""안과 전문의 AI로서 다음 OCT 검사 소견을 분석해 주세요.

소견: {findings_text}
ICD 코드: {icd_code or '미지정'}

분석 항목:
1. 망막 층 구조 이상 여부
2. 황반 상태 (두께, 부종, 원공 등)
3. 유리체망막 경계면 이상
4. 중증도 및 치료 시급성

개인정보 포함 금지."""

        response = await self._client.chat(
            messages=[{"role": "user", "content": prompt}],
            role=ModelRole.VISION,
        )

        return {
            "raw_analysis": response.content,
            "icd_code": icd_code,
            "model_used": response.model,
        }

    async def analyze_visual_field(
        self,
        findings_text: str,
        iop_left: float | None = None,
        iop_right: float | None = None,
    ) -> dict:
        """시야 검사 소견 + 안압 종합 분석"""
        iop_info = ""
        if iop_left or iop_right:
            iop_info = f"\n안압: 좌 {iop_left or 'N/A'} mmHg, 우 {iop_right or 'N/A'} mmHg"

        prompt = f"""안과 전문의 AI로서 다음 시야 검사 결과를 분석해 주세요.{iop_info}

시야 검사 소견: {findings_text}

분석 항목:
1. 시야 결손 패턴 (중심/주변/Arcuate scotoma 등)
2. MD(Mean Deviation), PSD 해석
3. 녹내장 진행 가능성 평가
4. 추적 관찰 권고 사항

개인정보 포함 금지."""

        response = await self._client.chat(
            messages=[{"role": "user", "content": prompt}],
            role=ModelRole.HEAVY,
        )

        return {
            "raw_analysis": response.content,
            "iop_left": iop_left,
            "iop_right": iop_right,
            "model_used": response.model,
        }
