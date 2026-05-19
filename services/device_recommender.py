"""MEDI-EYE-h (의료기기) + MEDI-EYE-w (Wellness) 추천 (R4-ML+)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DeviceRecommendation:
    type: str  # MEDI-EYE-h | MEDI-EYE-w
    device: str
    reason: str
    link: str | None = None
    nutrition: dict[str, str] | None = None


def _base_url() -> str:
    return (os.getenv("MEDI_EYE_BASE_URL") or "https://medi-eye.com").rstrip("/")


class DeviceRecommender:
    """DR 등급·환자 프로필 기반 기기/Wellness 추천."""

    async def recommend(
        self,
        dr_grade: int,
        patient_profile: dict[str, Any] | None = None,
    ) -> list[DeviceRecommendation]:
        profile = patient_profile or {}
        recommendations: list[DeviceRecommendation] = []
        base = _base_url()

        # MEDI-EYE-h — DR ≥ 2 또는 IOP 이상
        iop_high = False
        for key in ("iop_left", "iop_right"):
            try:
                if float(profile.get(key, 0)) > 21:
                    iop_high = True
            except (TypeError, ValueError):
                pass

        if dr_grade >= 2 or iop_high:
            recommendations.append(
                DeviceRecommendation(
                    type="MEDI-EYE-h",
                    device="휴대용 안압계",
                    reason="당뇨망막병증·녹내장 위험 모니터링",
                    link=f"{base}/devices/tonometer",
                )
            )
            if dr_grade >= 2:
                recommendations.append(
                    DeviceRecommendation(
                        type="MEDI-EYE-h",
                        device="CGM 연동 혈당계",
                        reason="DR 진행과 혈당 변동 상관 모니터링",
                        link=f"{base}/devices/cgm",
                    )
                )

        if dr_grade >= 3:
            recommendations.append(
                DeviceRecommendation(
                    type="MEDI-EYE-h",
                    device="OCT 홈케어 연동(병원 연계)",
                    reason="망막 부종·황반 변화 추적",
                    link=f"{base}/devices/oct-link",
                )
            )

        # MEDI-EYE-w — 모든 등급 예방
        recommendations.append(
            DeviceRecommendation(
                type="MEDI-EYE-w",
                device="루테인·제아잔틴 보충제",
                reason="황반 보호 및 산화 스트레스 완화",
                link=f"{base}/wellness/lutein",
                nutrition={"lutein": "10mg/day", "zeaxanthin": "2mg/day"},
            )
        )
        recommendations.append(
            DeviceRecommendation(
                type="MEDI-EYE-w",
                device="스마트 안경 (눈 피로 모니터링)",
                reason="디지털 눈 피로·깜빡임 관리",
                link=f"{base}/wellness/smart-glasses",
            )
        )
        if profile.get("has_diabetes") or dr_grade >= 1:
            recommendations.append(
                DeviceRecommendation(
                    type="MEDI-EYE-w",
                    device="스마트워치 (혈당·혈압)",
                    reason="대사 리스크 통합 모니터링",
                    link=f"{base}/wellness/watch",
                )
            )

        return recommendations


__all__ = ["DeviceRecommender", "DeviceRecommendation"]
