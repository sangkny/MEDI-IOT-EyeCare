# MEDI-IOT-EyeCare/services/cache.py
"""
CacheService — Redis 스마트 캐싱 [Week 3 Day 4]

역할:
  1. AI 진단 결과 캐시 (patient_id + 검사 해시 기준, 24시간)
  2. 임베딩 벡터 캐시 (텍스트 해시 기준, 7일)
  3. 환자 추이 분석 캐시 (1시간)
  4. 캐시 히트/미스 통계

성능 효과:
  - 동일 소견 재분석: ~85초 → ~0.1초 (850x 빠름)
  - 동일 쿼리 임베딩: ~2초 → ~0.1초 (20x 빠름)

사용법:
    cache = CacheService()
    await cache.set_diagnosis(patient_id, exam_hash, result)
    cached = await cache.get_diagnosis(patient_id, exam_hash)
"""
import hashlib
import json
import logging
from typing import Any

import redis.asyncio as aioredis

from config import get_settings

log = logging.getLogger("services.cache")

# TTL 상수 (초)
TTL_DIAGNOSIS  = 24 * 3600    # 진단 결과: 24시간
TTL_EMBEDDING  = 7  * 86400   # 임베딩:   7일
TTL_TREND      = 3600          # 추이 분석: 1시간
TTL_PATIENT    = 300           # 환자 정보: 5분


class CacheService:
    """
    Redis 기반 의료 데이터 캐싱 서비스

    캐시 키 구조:
      medi:{type}:{hash}
      예: medi:diagnosis:a3b4c5d6...
          medi:embed:f7e8d9c0...
    """

    _client: aioredis.Redis | None = None

    def __init__(self) -> None:
        settings = get_settings()
        self._redis_url = settings.redis_url
        self._prefix    = "medi"
        # 통계
        self._hits      = 0
        self._misses    = 0

    async def _get_client(self) -> aioredis.Redis:
        if self._client is None or not await self._ping():
            self._client = await aioredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
        return self._client

    async def _ping(self) -> bool:
        try:
            return bool(await self._client.ping()) if self._client else False
        except Exception:
            return False

    def _key(self, *parts: str) -> str:
        return f"{self._prefix}:" + ":".join(parts)

    @staticmethod
    def _hash(*values: str) -> str:
        """여러 값을 SHA-256으로 해싱"""
        combined = "|".join(str(v) for v in values)
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    # ══════════════════════════════════════════════════════
    # AI 진단 결과 캐시
    # ══════════════════════════════════════════════════════

    def _diagnosis_hash(self, patient_id: str, exam_findings: str) -> str:
        return self._hash(patient_id, exam_findings[:500])

    async def get_diagnosis(
        self, patient_id: str, exam_findings: str
    ) -> dict | None:
        """진단 결과 캐시 조회"""
        try:
            client = await self._get_client()
            key    = self._key("diagnosis", self._diagnosis_hash(patient_id, exam_findings))
            data   = await client.get(key)
            if data:
                self._hits += 1
                log.info(f"[Cache] HIT diagnosis: {key[-8:]}")
                return json.loads(data)
            self._misses += 1
            return None
        except Exception as e:
            log.warning(f"[Cache] get_diagnosis 실패: {e}")
            return None

    async def set_diagnosis(
        self, patient_id: str, exam_findings: str, result: dict
    ) -> bool:
        """진단 결과 캐시 저장 (24시간)"""
        try:
            client = await self._get_client()
            key    = self._key("diagnosis", self._diagnosis_hash(patient_id, exam_findings))
            await client.setex(key, TTL_DIAGNOSIS, json.dumps(result, ensure_ascii=False))
            log.info(f"[Cache] SET diagnosis: {key[-8:]} (TTL={TTL_DIAGNOSIS}s)")
            return True
        except Exception as e:
            log.warning(f"[Cache] set_diagnosis 실패: {e}")
            return False

    # ══════════════════════════════════════════════════════
    # 임베딩 캐시
    # ══════════════════════════════════════════════════════

    async def get_embedding(self, text: str) -> list[float] | None:
        """임베딩 벡터 캐시 조회"""
        try:
            client = await self._get_client()
            key    = self._key("embed", self._hash(text))
            data   = await client.get(key)
            if data:
                self._hits += 1
                log.debug(f"[Cache] HIT embed: {key[-8:]}")
                return json.loads(data)
            self._misses += 1
            return None
        except Exception as e:
            log.warning(f"[Cache] get_embedding 실패: {e}")
            return None

    async def set_embedding(self, text: str, embedding: list[float]) -> bool:
        """임베딩 벡터 캐시 저장 (7일)"""
        try:
            client = await self._get_client()
            key    = self._key("embed", self._hash(text))
            await client.setex(key, TTL_EMBEDDING, json.dumps(embedding))
            log.debug(f"[Cache] SET embed: {key[-8:]} (TTL={TTL_EMBEDDING}s)")
            return True
        except Exception as e:
            log.warning(f"[Cache] set_embedding 실패: {e}")
            return False

    # ══════════════════════════════════════════════════════
    # 환자 추이 캐시
    # ══════════════════════════════════════════════════════

    async def get_trend(self, patient_id: str) -> dict | None:
        """환자 추이 분석 캐시 조회"""
        try:
            client = await self._get_client()
            key    = self._key("trend", patient_id)
            data   = await client.get(key)
            if data:
                self._hits += 1
                log.info(f"[Cache] HIT trend: {patient_id[:8]}")
                return json.loads(data)
            self._misses += 1
            return None
        except Exception as e:
            log.warning(f"[Cache] get_trend 실패: {e}")
            return None

    async def set_trend(self, patient_id: str, trend_data: dict) -> bool:
        """환자 추이 분석 캐시 저장 (1시간)"""
        try:
            client = await self._get_client()
            key    = self._key("trend", patient_id)
            await client.setex(key, TTL_TREND, json.dumps(trend_data, ensure_ascii=False, default=str))
            log.info(f"[Cache] SET trend: {patient_id[:8]} (TTL={TTL_TREND}s)")
            return True
        except Exception as e:
            log.warning(f"[Cache] set_trend 실패: {e}")
            return False

    async def invalidate_trend(self, patient_id: str) -> None:
        """새 검사 등록 시 추이 캐시 무효화"""
        try:
            client = await self._get_client()
            key    = self._key("trend", patient_id)
            await client.delete(key)
            log.info(f"[Cache] INVALIDATE trend: {patient_id[:8]}")
        except Exception as e:
            log.warning(f"[Cache] invalidate_trend 실패: {e}")

    # ══════════════════════════════════════════════════════
    # 유틸리티
    # ══════════════════════════════════════════════════════

    async def stats(self) -> dict:
        """캐시 히트율 통계"""
        total     = self._hits + self._misses
        hit_rate  = (self._hits / total * 100) if total > 0 else 0.0
        return {
            "hits":     self._hits,
            "misses":   self._misses,
            "total":    total,
            "hit_rate": round(hit_rate, 1),
        }

    async def ping(self) -> bool:
        """Redis 연결 확인"""
        try:
            client = await self._get_client()
            return await client.ping()
        except Exception:
            return False

    async def clear_all(self, pattern: str = "medi:*") -> int:
        """패턴에 매칭되는 모든 캐시 삭제 (테스트/개발용)"""
        try:
            client = await self._get_client()
            keys   = await client.keys(pattern)
            if keys:
                return await client.delete(*keys)
            return 0
        except Exception as e:
            log.warning(f"[Cache] clear_all 실패: {e}")
            return 0

    async def close(self) -> None:
        """Redis 연결 종료"""
        if self._client:
            await self._client.aclose()
            self._client = None


# 싱글톤 인스턴스 (FastAPI 의존성 주입용)
_cache_instance: CacheService | None = None


def get_cache() -> CacheService:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = CacheService()
    return _cache_instance
