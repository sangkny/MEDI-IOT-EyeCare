# MEDI-IOT-EyeCare/database.py
"""
SQLAlchemy 비동기 엔진 + 세션 팩토리
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config import get_settings

settings = get_settings()

# docker-compose 환경변수(postgresql://)를 asyncpg 드라이버로 자동 변환
_db_url = settings.database_url
if _db_url.startswith("postgresql://") and "+asyncpg" not in _db_url:
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(
    _db_url,
    echo=settings.debug,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    connect_args={"timeout": 10},
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """모든 SQLAlchemy 모델의 베이스 클래스"""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 의존성 주입용 DB 세션 생성기"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def enable_pgvector() -> None:
    """pgvector 확장 활성화 (Alembic 마이그레이션 전 필요)"""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

async def create_tables() -> None:
    """테이블 생성 (개발 환경 — 운영은 Alembic 사용)"""
    from models.medical import Patient, EyeExam, Diagnosis, EyeImage  # noqa: F401
    from models.knowledge import MedicalDocument, DocumentEmbedding, DiagnosisEmbedding  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
