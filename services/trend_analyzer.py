# MEDI-IOT-EyeCare/services/trend_analyzer.py
"""
TrendAnalyzer — 환자 시력/안압 추이 분석 [Week 3 Day 3]

역할:
  1. 환자의 복수 검사 기록에서 시력/안압 시계열 데이터 추출
  2. 추이 방향 분석 (improving/stable/worsening)
  3. 악화 징후 탐지 → 경고 메시지 생성

사용법:
    analyzer = TrendAnalyzer(db)
    trend = await analyzer.analyze(patient_id)
    print(trend.overall_status)   # "worsening"
    print(trend.alerts)           # ["안압 지속 상승", ...]
"""
from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.medical import EyeExam, Diagnosis

log = logging.getLogger("services.trend_analyzer")

TrendDirection = Literal["improving", "stable", "worsening", "insufficient_data"]


@dataclass
class TimeSeriesPoint:
    """단일 검사 시점 데이터"""
    exam_date:            date
    iop_left:             float | None
    iop_right:            float | None
    visual_acuity_left:   str | None
    visual_acuity_right:  str | None
    icd_code:             str | None
    exam_type:            str


@dataclass
class TrendSummary:
    """환자 추이 분석 결과"""
    patient_id:           str
    exam_count:           int
    date_range:           tuple[date, date] | None

    iop_trend:            TrendDirection
    vision_trend:         TrendDirection
    overall_status:       TrendDirection

    iop_series:           list[dict]    # [{date, left, right}]
    vision_series:        list[dict]    # [{date, left, right}]
    diagnosis_history:    list[dict]    # [{date, code, name, severity}]

    alerts:               list[str]     # 악화 징후 경고
    recommendations:      list[str]     # 추적 관찰 권고


def _parse_va(va_str: str | None) -> float | None:
    """시력 문자열 → float 변환 ('0.8' → 0.8, 'CF' → 0.01)"""
    if va_str is None:
        return None
    va_str = va_str.strip().lower()
    special = {"cf": 0.01, "hm": 0.005, "lp": 0.001, "nlp": 0.0}
    if va_str in special:
        return special[va_str]
    try:
        return float(va_str)
    except ValueError:
        return None


def _calc_trend(values: list[float]) -> TrendDirection:
    """
    숫자 시계열에서 추이 방향 계산
    - 3개 미만 데이터: insufficient_data
    - 선형 회귀 기울기로 판단
    """
    if len(values) < 2:
        return "insufficient_data"
    if len(values) == 2:
        diff = values[-1] - values[0]
        if abs(diff) < 0.5:
            return "stable"
        return "improving" if diff > 0 else "worsening"

    n    = len(values)
    x    = list(range(n))
    x_m  = statistics.mean(x)
    y_m  = statistics.mean(values)
    cov  = sum((xi - x_m) * (yi - y_m) for xi, yi in zip(x, values))
    var  = sum((xi - x_m) ** 2 for xi in x)
    slope = cov / var if var != 0 else 0.0

    if abs(slope) < 0.05:
        return "stable"
    return "improving" if slope > 0 else "worsening"


def _iop_trend_direction(values: list[float]) -> TrendDirection:
    """안압 추이: 상승(worsening), 하강(improving)"""
    raw = _calc_trend(values)
    if raw == "improving":
        return "worsening"   # 안압 상승 = 악화
    if raw == "worsening":
        return "improving"   # 안압 하강 = 개선
    return raw


class TrendAnalyzer:
    """
    환자 시력/안압 추이 분석기

    최근 12개 검사 기록을 바탕으로
    시력/안압의 변화 방향과 악화 징후를 탐지합니다.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def analyze(self, patient_id: str, limit: int = 12) -> TrendSummary:
        """
        환자의 검사 이력으로 추이 분석 수행

        Args:
            patient_id: 환자 UUID
            limit:      최근 N개 검사 기록 (기본 12)

        Returns:
            TrendSummary
        """
        log.info(f"[Trend] 분석 시작: patient={patient_id[:8]}")

        # 검사 기록 조회 (날짜순)
        exams = (await self._db.scalars(
            select(EyeExam)
            .where(EyeExam.patient_id == patient_id)
            .order_by(EyeExam.exam_date.asc())
            .limit(limit)
        )).all()

        if not exams:
            return TrendSummary(
                patient_id=patient_id, exam_count=0, date_range=None,
                iop_trend="insufficient_data", vision_trend="insufficient_data",
                overall_status="insufficient_data",
                iop_series=[], vision_series=[], diagnosis_history=[],
                alerts=[], recommendations=["검사 기록이 없습니다. 정기 검진을 권장합니다."],
            )

        # 시계열 데이터 구성
        iop_left_vals  = [e.iop_left  for e in exams if e.iop_left  is not None]
        iop_right_vals = [e.iop_right for e in exams if e.iop_right is not None]
        va_left_vals   = [_parse_va(e.visual_acuity_left)  for e in exams if e.visual_acuity_left]
        va_right_vals  = [_parse_va(e.visual_acuity_right) for e in exams if e.visual_acuity_right]

        # 추이 계산
        iop_vals_combined  = [(l + r) / 2 for l, r in zip(iop_left_vals, iop_right_vals)
                              if l is not None and r is not None]
        va_left_clean  = [v for v in va_left_vals  if v is not None]
        va_right_clean = [v for v in va_right_vals if v is not None]
        va_vals_combined   = [(l + r) / 2 for l, r in zip(va_left_clean, va_right_clean)
                              if l is not None and r is not None]

        iop_trend    = _iop_trend_direction(iop_vals_combined) if iop_vals_combined else "insufficient_data"
        vision_trend = _calc_trend(va_vals_combined) if va_vals_combined else "insufficient_data"

        # 종합 상태
        status_priority = {"worsening": 3, "stable": 2, "improving": 1, "insufficient_data": 0}
        overall_status  = max(
            [iop_trend, vision_trend],
            key=lambda s: status_priority.get(s, 0),
        )

        # 진단 이력 조회
        exam_ids = [e.id for e in exams]
        diagnoses_raw = []
        if exam_ids:
            for exam_id in exam_ids:
                diags = (await self._db.scalars(
                    select(Diagnosis)
                    .where(Diagnosis.exam_id == exam_id)
                    .order_by(Diagnosis.created_at.desc())
                    .limit(1)
                )).all()
                diagnoses_raw.extend(diags)

        # 시리즈 데이터 구성
        iop_series = [
            {
                "date":  e.exam_date.isoformat(),
                "left":  e.iop_left,
                "right": e.iop_right,
                "avg":   round((e.iop_left + e.iop_right) / 2, 1)
                         if e.iop_left and e.iop_right else None,
            }
            for e in exams if e.iop_left or e.iop_right
        ]

        vision_series = [
            {
                "date":  e.exam_date.isoformat(),
                "left":  _parse_va(e.visual_acuity_left),
                "right": _parse_va(e.visual_acuity_right),
                "left_raw":  e.visual_acuity_left,
                "right_raw": e.visual_acuity_right,
            }
            for e in exams if e.visual_acuity_left or e.visual_acuity_right
        ]

        diagnosis_history = [
            {
                "date":          next(
                    (e.exam_date.isoformat() for e in exams if e.id == d.exam_id), None
                ),
                "code":          d.diagnosis_code,
                "name":          d.diagnosis_name,
                "severity":      d.severity,
                "ontology_pass": d.ontology_passed,
            }
            for d in diagnoses_raw
        ]

        # 경고 및 권고 생성
        alerts, recommendations = self._generate_alerts(
            exams, iop_trend, vision_trend, iop_vals_combined, va_vals_combined
        )

        date_range = (exams[0].exam_date, exams[-1].exam_date) if exams else None

        summary = TrendSummary(
            patient_id=patient_id,
            exam_count=len(exams),
            date_range=date_range,
            iop_trend=iop_trend,
            vision_trend=vision_trend,
            overall_status=overall_status,
            iop_series=iop_series,
            vision_series=vision_series,
            diagnosis_history=diagnosis_history,
            alerts=alerts,
            recommendations=recommendations,
        )
        log.info(f"[Trend] 완료: {overall_status} | alerts={len(alerts)}")
        return summary

    def _generate_alerts(
        self,
        exams: list[EyeExam],
        iop_trend: TrendDirection,
        vision_trend: TrendDirection,
        iop_vals: list[float],
        va_vals: list[float],
    ) -> tuple[list[str], list[str]]:
        """악화 징후 경고 + 추적 관찰 권고 생성"""
        alerts:          list[str] = []
        recommendations: list[str] = []

        # 안압 경고
        if iop_vals:
            latest_iop = iop_vals[-1]
            if latest_iop > 21:
                alerts.append(f"안압 고위험: 최근 평균 {latest_iop:.1f} mmHg (정상 ≤21)")
            elif latest_iop > 18:
                alerts.append(f"안압 경계: 최근 평균 {latest_iop:.1f} mmHg (주의 관찰)")

        if iop_trend == "worsening" and len(iop_vals) >= 2:
            delta = iop_vals[-1] - iop_vals[0]
            alerts.append(f"안압 지속 상승: {delta:+.1f} mmHg 증가 추세")
            recommendations.append("녹내장 전문의 진료 및 안압 하강제 처방 검토")

        # 시력 경고
        if va_vals:
            latest_va = va_vals[-1]
            if latest_va < 0.3:
                alerts.append(f"심각한 시력 저하: 최근 평균 {latest_va:.2f}")
            elif latest_va < 0.5:
                alerts.append(f"시력 저하 주의: 최근 평균 {latest_va:.2f}")

        if vision_trend == "worsening" and len(va_vals) >= 2:
            delta = va_vals[-1] - va_vals[0]
            alerts.append(f"시력 지속 저하: {delta:.2f} 감소 추세")
            recommendations.append("안과 전문의 조기 진료 권고")

        # 기본 권고
        if not recommendations:
            if len(exams) < 3:
                recommendations.append("정기 검진 이력이 부족합니다 — 3개월마다 안과 검진 권장")
            else:
                recommendations.append("현재 상태를 유지하며 정기 추적 관찰 지속")

        return alerts, recommendations
