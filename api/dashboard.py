"""
관리자 대시보드 API (Week 4 Day 1)

GET /dashboard/stats     — 검사·환자 카운터, 진단 분포, AI–검사 ICD 일치율
GET /dashboard/alerts     — 긴급 추적 후보, OntologyValidator 경고 환자
GET /dashboard/llm-usage — 일간 LLM 호출·추정 토큰, provider bucket
"""
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from auth.dependencies import require_role
from auth.policy import policy_require
from schemas.dashboard import (
    DashboardStatsResponse,
    DashboardAlertsResponse,
    DashboardLLMUsageResponse,
)
from schemas.admin_audit import AuditLogListResponse
from services.dashboard_service import (
    load_dashboard_stats,
    load_dashboard_alerts,
    load_llm_dashboard,
)
from services.audit_log_service import load_audit_logs

log = logging.getLogger("api.dashboard")
router = APIRouter()


_STATS_DESC = """
**오늘(UTC 자정 기준)**  
- 새 검사(`eye_exams.created_at`), 신규 환자(`patients.created_at`) 건수

**진단별 분포**  
- 최근 30일 `diagnoses` 기준 카테고리:
  당뇨망막병증(H36 계열 및 H35.0), 황반/망막(H35), 녹내장(H40), 정상(normal severity·정상 포함), 기타

**AI 정합도 프록시**  
- 동일 검사 레코드에 대해 검사 ICD(`eye_exams.icd_code`)와 AI `diagnosis_code` 문자열 동일 여부 비율
  (향후 의사 금판 필드 저장 시 교체 가능)
"""


@router.get(
    "/stats",
    response_model=DashboardStatsResponse,
    summary="대시보드 통계",
    description=_STATS_DESC,
)
async def dashboard_stats(
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(policy_require("medi-iot", "dashboard_stats")),
) -> DashboardStatsResponse:
    """관리 통계 KPI."""
    return await load_dashboard_stats(db)


_ALERTS_DESC = """
- **긴급 추적 필요**: 최근 30일 내 진단이 있는 환자 중 `TrendAnalyzer` 가
  안압/시력 악화 징후(`alerts` 또는 전체 상태 `worsening`)인 경우 표시합니다.
  (표본 과다 방지 최대 약 35명 스캔)
- **OntologyValidator 경고**: 최근 AI 진단 중 `ontology_passed=false`
"""


@router.get(
    "/alerts",
    response_model=DashboardAlertsResponse,
    summary="대시보드 알림",
    description=_ALERTS_DESC,
)
async def dashboard_alerts(
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(policy_require("medi-iot", "dashboard_stats")),
) -> DashboardAlertsResponse:
    """긴급 환자 + OntologyValidator 미통과 환자 목록."""
    return await load_dashboard_alerts(db)


_LLM_DESC = """
Redis에 누적된 **금일 LLM 호출 통계**(UTC 날짜 기준 버킷)를 반환합니다.

- 각 Orchestrator lore 항목, `LLM.chat`, embed 요청이 집계에 포함될 수 있습니다.
- LM Studio 로컬 Provider는 토큰 미표시 경우가 많아 문자 길이 기반 근삿값을 사용합니다.
"""


@router.get(
    "/llm-usage",
    response_model=DashboardLLMUsageResponse,
    summary="LLM 사용량",
    description=_LLM_DESC,
)
async def dashboard_llm_usage(
    _: dict = Depends(policy_require("medi-iot", "dashboard_stats")),
) -> DashboardLLMUsageResponse:
    return await load_llm_dashboard()


@router.get(
    "/audit-logs",
    response_model=AuditLogListResponse,
    summary="감사 로그 목록 (admin)",
)
async def dashboard_audit_logs(
    db: AsyncSession = Depends(get_db),
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    decision: str | None = Query(default=None),
    _admin: dict = Depends(require_role("admin")),
) -> AuditLogListResponse:
    return await load_audit_logs(
        db, from_date=from_date, to_date=to_date, decision=decision
    )
