"""DR 등급 기반 주변 병의원 추천 (R4-ML+).

데이터 소스 (env 설정 시 live, 없으면 fallback):
  - 건강보험심사평가원 Open API
  - 카카오맵 Local API
  - 공공데이터포털 의료기관 API
"""
from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass

import httpx

log = logging.getLogger("services.hospital_recommender")


@dataclass(frozen=True)
class HospitalCandidate:
    name: str
    address: str
    distance_km: float
    specialty: str
    phone: str | None
    evaluation_score: float
    map_url: str | None
    urgency: str
    data_source: str = "fallback"


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlng / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _specialty_for_grade(dr_grade: int) -> tuple[str, str]:
    if dr_grade >= 3:
        return "망막 전문 안과", "즉시"
    if dr_grade >= 2:
        return "안과", "1개월 내"
    return "안과 또는 내과", "정기 검진"


class HospitalRecommender:
    """위치·DR 등급 기반 병원 추천."""

    def __init__(self) -> None:
        self._hira_key = (os.getenv("HIRA_API_KEY") or "").strip()
        self._kakao_key = (os.getenv("KAKAO_API_KEY") or "").strip()
        self._public_key = (os.getenv("PUBLIC_DATA_API_KEY") or "").strip()

    async def recommend(
        self,
        dr_grade: int,
        location: tuple[float, float],
        *,
        radius_km: float = 5.0,
        limit: int = 5,
    ) -> list[HospitalCandidate]:
        specialty, urgency = _specialty_for_grade(dr_grade)
        lat, lng = location

        hospitals: list[HospitalCandidate] = []
        if self._kakao_key:
            try:
                hospitals = await self._fetch_kakao(lat, lng, specialty, radius_km, urgency)
            except Exception as exc:
                log.warning("Kakao hospital fetch failed: %s", exc)

        if not hospitals and self._public_key:
            try:
                hospitals = await self._fetch_public_data(lat, lng, specialty, urgency)
            except Exception as exc:
                log.warning("Public data hospital fetch failed: %s", exc)

        if not hospitals:
            hospitals = self._fallback_hospitals(lat, lng, specialty, urgency)

        return sorted(hospitals, key=lambda h: h.evaluation_score, reverse=True)[:limit]

    async def _fetch_kakao(
        self,
        lat: float,
        lng: float,
        specialty: str,
        radius_km: float,
        urgency: str,
    ) -> list[HospitalCandidate]:
        query = "안과" if "안과" in specialty else specialty
        url = "https://dapi.kakao.com/v2/local/search/keyword.json"
        headers = {"Authorization": f"KakaoAK {self._kakao_key}"}
        params = {
            "query": query,
            "x": lng,
            "y": lat,
            "radius": int(radius_km * 1000),
            "size": 10,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()

        out: list[HospitalCandidate] = []
        for doc in data.get("documents") or []:
            try:
                dlat = float(doc.get("y") or lat)
                dlng = float(doc.get("x") or lng)
            except (TypeError, ValueError):
                dlat, dlng = lat, lng
            dist = _haversine_km(lat, lng, dlat, dlng)
            out.append(
                HospitalCandidate(
                    name=str(doc.get("place_name") or "의료기관"),
                    address=str(doc.get("road_address_name") or doc.get("address_name") or ""),
                    distance_km=round(dist, 2),
                    specialty=specialty,
                    phone=str(doc.get("phone") or "") or None,
                    evaluation_score=max(0.5, 1.0 - dist / max(radius_km, 1)),
                    map_url=str(doc.get("place_url") or "") or None,
                    urgency=urgency,
                    data_source="kakao",
                )
            )
        return out

    async def _fetch_public_data(
        self,
        lat: float,
        lng: float,
        specialty: str,
        urgency: str,
    ) -> list[HospitalCandidate]:
        """공공데이터포털 — 키·엔드포인트는 운영자 `.env` 에 맞게 확장."""
        _ = self._public_key
        return []

    def _fallback_hospitals(
        self,
        lat: float,
        lng: float,
        specialty: str,
        urgency: str,
    ) -> list[HospitalCandidate]:
        """API 키 없을 때 서울 중심 샘플 (개발·데모)."""
        samples = [
            ("서울대학교병원 안과", "서울 종로구 대학로 101", 37.5799, 126.9968, 4.8),
            ("세브란스병원 안과", "서울 서대문구 연세로 50-1", 37.5622, 126.9408, 4.7),
            ("아산병원 안과", "서울 송파구 올림픽로43길 88", 37.5267, 127.1088, 4.7),
            ("강남세브란스 안과", "서울 강남구 일원로 211", 37.4190, 127.1262, 4.6),
            ("서울성모병원 안과", "서울 서초구 반포대로 222", 37.5016, 127.0048, 4.5),
        ]
        out: list[HospitalCandidate] = []
        for name, addr, hlat, hlng, score in samples:
            dist = _haversine_km(lat, lng, hlat, hlng)
            out.append(
                HospitalCandidate(
                    name=name,
                    address=addr,
                    distance_km=round(dist, 2),
                    specialty=specialty,
                    phone="02-000-0000",
                    evaluation_score=score - min(dist * 0.02, 0.5),
                    map_url=f"https://map.kakao.com/link/map/{name},{hlat},{hlng}",
                    urgency=urgency,
                    data_source="fallback",
                )
            )
        return out


__all__ = ["HospitalRecommender", "HospitalCandidate"]
