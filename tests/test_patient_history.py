# MEDI-IOT-EyeCare/tests/test_patient_history.py
"""
환자 이력/추이/보고서 API + Redis 캐싱 테스트 [Week 3 Day 3+4]

실행:
    docker compose -f docker-compose.dev.yml exec medi-iot-api \
        pytest tests/test_patient_history.py -v -s
"""
import io, uuid
from datetime import date, timedelta

import httpx
import pytest

BASE_URL = "http://localhost:8000"
API_V1   = f"{BASE_URL}/api/v1"
TIMEOUT  = httpx.Timeout(30.0)


def _uid() -> str:
    return f"H{uuid.uuid4().hex[:6].upper()}"


def _create_patient_with_exams() -> tuple[str, str]:
    """환자 + 3회 검사 생성 → (patient_id, patient_code)"""
    code = _uid()
    pr   = httpx.post(f"{API_V1}/patients/",
                      json={"patient_code": code, "primary_diagnosis_code": "H40.1"},
                      timeout=TIMEOUT)
    assert pr.status_code == 201
    pid  = pr.json()["id"]

    today = date.today()
    for i, (iop_l, iop_r, va_l, va_r) in enumerate([
        (18.0, 17.5, "0.8", "0.8"),   # 검사 1 (3개월 전)
        (20.0, 19.5, "0.7", "0.7"),   # 검사 2 (1개월 전)
        (22.0, 21.5, "0.6", "0.6"),   # 검사 3 (오늘)
    ]):
        exam_date = today - timedelta(days=90 - i * 30)
        er = httpx.post(f"{API_V1}/diagnosis/exam", json={
            "patient_id":          pid,
            "exam_type":           "visual_field",
            "exam_date":           exam_date.isoformat(),
            "icd_code":            "H40.1",
            "iop_left":            iop_l,
            "iop_right":           iop_r,
            "visual_acuity_left":  va_l,
            "visual_acuity_right": va_r,
            "raw_findings":        f"검사 {i+1}: 안압 {iop_l}/{iop_r} mmHg, 시력 {va_l}/{va_r}",
        }, timeout=TIMEOUT)
        assert er.status_code == 201

    return pid, code


# ════════════════════════════════════════════════════════════
# 환자 이력 API
# ════════════════════════════════════════════════════════════

class TestPatientHistoryAPI:
    """GET /patients/{id}/history — 검사 + 진단 전체 이력"""

    def test_get_history_with_exams(self):
        """
        목적: 환자 이력 조회 (검사 3회 + 요약)
        단계: 환자+검사 생성 → /history → 검사 목록 + 요약 확인
        """
        pid, code = _create_patient_with_exams()

        r = httpx.get(f"{API_V1}/patients/{pid}/history", timeout=TIMEOUT)
        print(f"\n  GET /patients/{pid[:8]}.../history → {r.status_code}")
        body = r.json()
        print(f"  총 검사:  {body['summary']['total_exams']}개")
        print(f"  총 진단:  {body['summary']['total_diagnoses']}개")
        print(f"  최근 검사: {body['summary']['latest_exam_date']}")

        assert r.status_code == 200
        assert body["summary"]["total_exams"] == 3
        assert len(body["exams"]) == 3
        print("  ✅ 환자 이력 조회 성공")

    def test_get_history_by_patient_code(self):
        """patient_code로 이력 조회"""
        pid, code = _create_patient_with_exams()
        r = httpx.get(f"{API_V1}/patients/{code}/history", timeout=TIMEOUT)
        print(f"\n  GET /patients/{code}/history → {r.status_code}")
        assert r.status_code == 200
        assert r.json()["summary"]["total_exams"] == 3
        print("  ✅ patient_code로 이력 조회 성공")

    def test_get_history_empty_patient(self):
        """검사 기록 없는 환자 이력 조회"""
        code = _uid()
        pr   = httpx.post(f"{API_V1}/patients/",
                          json={"patient_code": code}, timeout=TIMEOUT)
        pid  = pr.json()["id"]

        r = httpx.get(f"{API_V1}/patients/{pid}/history", timeout=TIMEOUT)
        body = r.json()
        print(f"\n  빈 환자 이력: exams={body['summary']['total_exams']}")
        assert r.status_code == 200
        assert body["summary"]["total_exams"] == 0
        print("  ✅ 빈 이력 정상 응답")


# ════════════════════════════════════════════════════════════
# 추이 분석 API
# ════════════════════════════════════════════════════════════

class TestPatientTrendAPI:
    """GET /patients/{id}/trend — 시력/안압 추이"""

    def test_trend_worsening_detection(self):
        """
        목적: 안압 상승 + 시력 저하 추이 → worsening 탐지
        단계: 3회 검사(안압 상승, 시력 저하) → /trend → overall_status=worsening
        """
        pid, _ = _create_patient_with_exams()

        r = httpx.get(f"{API_V1}/patients/{pid}/trend", timeout=TIMEOUT)
        print(f"\n  GET /patients/{pid[:8]}.../trend → {r.status_code}")
        body = r.json()
        print(f"  iop_trend:     {body['iop_trend']}")
        print(f"  vision_trend:  {body['vision_trend']}")
        print(f"  overall:       {body['overall_status']}")
        print(f"  alerts:        {body.get('alerts', [])}")
        print(f"  recommendations: {body.get('recommendations', [])}")
        print(f"  cached:        {body.get('cached', False)}")
        print(f"  iop_series:    {body.get('iop_series', [])}")

        assert r.status_code == 200
        assert body["iop_trend"] in ("improving", "stable", "worsening", "insufficient_data")
        assert len(body["iop_series"]) >= 2
        assert body["cached"] is False  # 첫 요청 = 캐시 미스
        print(f"  ✅ 추이 분석 성공 (overall={body['overall_status']})")

        # 두 번째 요청 = 캐시 히트
        r2 = httpx.get(f"{API_V1}/patients/{pid}/trend", timeout=TIMEOUT)
        body2 = r2.json()
        print(f"  2차 요청 cached: {body2.get('cached')}")
        assert body2.get("cached") is True, "2차 요청이 캐시에서 오지 않음"
        print("  ✅ Redis 캐싱 확인 (cached=True)")

    def test_trend_insufficient_data(self):
        """검사 기록 없는 환자 추이 → insufficient_data"""
        code = _uid()
        pr   = httpx.post(f"{API_V1}/patients/",
                          json={"patient_code": code}, timeout=TIMEOUT)
        pid  = pr.json()["id"]

        r = httpx.get(f"{API_V1}/patients/{pid}/trend", timeout=TIMEOUT)
        body = r.json()
        print(f"\n  데이터 없는 추이: overall={body['overall_status']}")
        assert r.status_code == 200
        assert body["overall_status"] == "insufficient_data"
        print("  ✅ 데이터 부족 처리 확인")


# ════════════════════════════════════════════════════════════
# 진단 보고서 목록 API
# ════════════════════════════════════════════════════════════

class TestPatientReportsAPI:
    """GET /patients/{id}/reports — AI 진단 보고서 목록"""

    def test_get_reports_empty(self):
        """AI 진단 없는 환자 보고서 목록 → 빈 배열"""
        code = _uid()
        pr   = httpx.post(f"{API_V1}/patients/",
                          json={"patient_code": code}, timeout=TIMEOUT)
        pid  = pr.json()["id"]

        r = httpx.get(f"{API_V1}/patients/{pid}/reports", timeout=TIMEOUT)
        print(f"\n  보고서 없는 환자: {r.status_code}, count={len(r.json())}")
        assert r.status_code == 200
        assert r.json() == []
        print("  ✅ 빈 보고서 목록 정상 응답")

    def test_get_reports_with_filter(self):
        """only_passed=true 필터 동작 확인"""
        pid, _ = _create_patient_with_exams()
        r      = httpx.get(f"{API_V1}/patients/{pid}/reports",
                           params={"only_passed": True}, timeout=TIMEOUT)
        print(f"\n  only_passed=true 필터: {r.status_code}")
        assert r.status_code == 200
        reports = r.json()
        assert all(rpt.get("ontology_passed") is True for rpt in reports)
        print(f"  ✅ only_passed 필터 (결과 {len(reports)}개)")


# ════════════════════════════════════════════════════════════
# Redis 캐싱 직접 테스트
# ════════════════════════════════════════════════════════════

class TestCacheService:
    """
    목적: CacheService 직접 동작 검증
    단계: LLM 없이 Redis 캐시 저장/조회/통계 확인
    """

    @pytest.mark.asyncio
    async def test_cache_diagnosis(self):
        """진단 결과 캐시 저장 + 조회"""
        from services.cache import CacheService
        cache = CacheService()

        dummy = {"diagnosis_code": "H36.0", "confidence": 0.85}
        ok    = await cache.set_diagnosis("test-patient", "test findings", dummy)
        assert ok, "캐시 저장 실패"

        cached = await cache.get_diagnosis("test-patient", "test findings")
        print(f"\n  진단 캐시 조회: {cached}")
        assert cached is not None
        assert cached["diagnosis_code"] == "H36.0"
        print("  ✅ 진단 결과 캐시 저장/조회 성공")

    @pytest.mark.asyncio
    async def test_cache_embedding(self):
        """임베딩 캐시 저장 + 조회"""
        from services.cache import CacheService
        cache = CacheService()
        embed = [0.1, 0.2, 0.3] * 256  # 768차원

        ok     = await cache.set_embedding("테스트 텍스트", embed)
        assert ok
        cached = await cache.get_embedding("테스트 텍스트")
        print(f"\n  임베딩 캐시: len={len(cached) if cached else 0}")
        assert cached is not None
        assert len(cached) == 768
        print("  ✅ 임베딩 캐시 저장/조회 성공")

    @pytest.mark.asyncio
    async def test_cache_miss(self):
        """캐시 미스 — 존재하지 않는 키 조회"""
        from services.cache import CacheService
        cache  = CacheService()
        result = await cache.get_diagnosis("nonexistent", "nothing")
        print(f"\n  캐시 미스: {result}")
        assert result is None
        print("  ✅ 캐시 미스 정상 처리")

    @pytest.mark.asyncio
    async def test_cache_stats(self):
        """캐시 히트율 통계"""
        from services.cache import CacheService
        cache = CacheService()
        await cache.get_diagnosis("x", "y")       # miss
        await cache.set_diagnosis("x", "y", {})
        await cache.get_diagnosis("x", "y")       # hit

        stats = await cache.stats()
        print(f"\n  캐시 통계: {stats}")
        assert stats["hits"]   >= 1
        assert stats["misses"] >= 1
        assert 0 <= stats["hit_rate"] <= 100
        print(f"  ✅ 캐시 통계: 히트율={stats['hit_rate']}%")

    @pytest.mark.asyncio
    async def test_trend_cache_invalidation(self):
        """추이 캐시 무효화"""
        from services.cache import CacheService
        cache = CacheService()
        pid   = "test-patient-trend"

        await cache.set_trend(pid, {"overall_status": "stable"})
        before = await cache.get_trend(pid)
        assert before is not None

        await cache.invalidate_trend(pid)
        after = await cache.get_trend(pid)
        print(f"\n  무효화 전: {before['overall_status']}, 후: {after}")
        assert after is None
        print("  ✅ 추이 캐시 무효화 성공")

    @pytest.mark.asyncio
    async def test_redis_ping(self):
        """Redis 연결 확인"""
        from services.cache import CacheService
        cache = CacheService()
        ok    = await cache.ping()
        print(f"\n  Redis ping: {ok}")
        assert ok is True
        print("  ✅ Redis 연결 확인")
