# MEDI-IOT-EyeCare/api/health.py
"""
헬스 체크 엔드포인트
GET /health         — Kubernetes/Docker HEALTHCHECK 호환
GET /health/detail  — 상세 상태 (LLM, DB, Redis 연결 확인)
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from config import get_settings, Settings
from database import get_db
from schemas.medical import HealthResponse

log = logging.getLogger("api.health")
router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="헬스 체크")
async def health_check(
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> HealthResponse:
    """
    서비스 기본 헬스 체크.
    DB 연결 확인 포함 — 실패 시 503 반환.
    """
    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        log.warning(f"DB 연결 실패: {e}")

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        service=settings.service_name,
        version=settings.version,
        llm_provider=settings.llm_provider,
        db_connected=db_ok,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/health/detail", summary="상세 헬스 체크")
async def health_detail(
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    LLM Provider 연결 상태 포함 상세 헬스 체크.
    """
    result: dict = {
        "service": settings.service_name,
        "version": settings.version,
        "environment": settings.environment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {},
    }

    # LLM 연결 확인
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.local_base_url}/models")
            result["checks"]["llm"] = {
                "status": "ok" if resp.status_code == 200 else "error",
                "provider": settings.llm_provider,
                "base_url": settings.local_base_url,
            }
    except Exception as e:
        result["checks"]["llm"] = {"status": "error", "error": str(e)}

    # Redis 연결 확인
    try:
        import redis.asyncio as aioredis
        r = await aioredis.from_url(settings.redis_url, socket_connect_timeout=3)
        await r.ping()
        await r.aclose()
        result["checks"]["redis"] = {"status": "ok"}
    except Exception as e:
        result["checks"]["redis"] = {"status": "error", "error": str(e)}

    overall = "ok" if all(
        v.get("status") == "ok" for v in result["checks"].values()
    ) else "degraded"
    result["status"] = overall

    return result
