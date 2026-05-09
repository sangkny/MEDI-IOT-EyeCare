# MEDI-IOT-EyeCare/main.py
"""
MEDI-IOT EyeCare — FastAPI 엔트리포인트

아키텍처:
  shared-libraries (LLM + Ontology + Agents)
      ↓
  services/ (EyeAnalyzer, ReportGenerator)
      ↓
  api/ (FastAPI 라우터)
      ↓
  PostgreSQL (환자/검사/진단 데이터)

실행:
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""
import logging

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from api import api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
log = logging.getLogger("main")
settings = get_settings()


# ════════════════════════════════════════════════════════════
# Lifespan (startup / shutdown)
# ════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """앱 시작 시 DB 테이블 생성, 종료 시 정리"""
    log.info(f"🚀 {settings.service_name} v{settings.version} 시작")
    log.info(f"   환경: {settings.environment}")
    log.info(f"   LLM:  {settings.llm_provider} ({settings.local_base_url})")

    # 테이블 생성은 Alembic이 관리 (alembic upgrade head)
    # create_tables() 직접 호출 금지
    log.info("   DB 스키마: Alembic 마이그레이션으로 관리")

    yield

    log.info(f"👋 {settings.service_name} 종료")


# ════════════════════════════════════════════════════════════
# FastAPI 앱 정의
# ════════════════════════════════════════════════════════════

app = FastAPI(
    title="MEDI-IOT EyeCare API",
    description="""
## MEDI-IOT EyeCare — 안과 AI 진단 플랫폼

### 주요 기능
- **환자 관리**: 등록, 조회, PII 암호화 저장
- **검사 기록**: OCT, 안저, 시야 검사 등 다양한 검사 유형 지원
- **AI 진단**: shared-libraries Orchestrator (CONSENSUS 전략) 기반
  - FAST 모델: gemma-4-e4b (초안 생성)
  - HEAVY 모델: gemma-4-26b-a4b (의료 정확성 검토)
  - OntologyValidator: MEDICAL 도메인 규칙 자동 검증

### 설계 원칙
- 환자 PII는 암호화하여 저장 (응답 시 마스킹)
- 의료 안전을 위해 CONSENSUS 전략 사용 (두 모델이 합의해야 PASS)
- Circuit Breaker: 최대 2회 반복 후 현재 최선 결과 반환
    """,
    version=settings.version,
    lifespan=lifespan,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
)

# ── CORS ──────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 전역 예외 처리 ─────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.error(f"처리되지 않은 예외: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "내부 서버 오류가 발생했습니다."},
    )


# ── 라우터 등록 ────────────────────────────────────────────

app.include_router(api_router, prefix="/api/v1")

# /health는 prefix 없이 (Docker HEALTHCHECK 호환)
from api.health import router as health_router  # noqa: E402
app.include_router(health_router)


# ── 개발용 직접 실행 ────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
