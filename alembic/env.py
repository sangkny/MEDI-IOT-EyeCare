# MEDI-IOT-EyeCare/alembic/env.py
"""
Alembic 마이그레이션 환경 설정

핵심:
  - DATABASE_URL 환경변수에서 DB URL을 읽음
  - postgresql:// → postgresql+psycopg2:// 자동 변환 (동기 드라이버 사용)
  - models/medical.py의 Base.metadata를 target_metadata로 사용
  - --autogenerate 시 Patient, EyeExam, Diagnosis 테이블 감지
"""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# ── Python 경로에 /app 추가 ────────────────────────────────
# docker exec 시 /app이 PYTHONPATH에 없을 수 있으므로 명시적 추가
sys.path.insert(0, "/app")
sys.path.insert(0, "/app/shared-libraries")

# ── ORM 모델 import (autogenerate 감지용) ─────────────────
from database import Base  # noqa: E402
import models.medical  # noqa: F401, E402 — 모델 등록

# ── Alembic Config ─────────────────────────────────────────
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# ════════════════════════════════════════════════════════════
# DB URL 헬퍼
# ════════════════════════════════════════════════════════════

def get_sync_url() -> str:
    """
    환경변수 DATABASE_URL을 읽어 동기 드라이버(psycopg2)로 변환.

    Alembic은 동기 연결을 사용하므로 asyncpg → psycopg2 변환 필요.
    """
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql://dev:dev@postgres:5432/mediiot",
    )
    # asyncpg 드라이버 제거 → psycopg2 사용 (Alembic 호환)
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    url = url.replace("postgresql+psycopg2://", "postgresql://")
    return url


# ════════════════════════════════════════════════════════════
# 오프라인 마이그레이션 (SQL 스크립트 생성)
# ════════════════════════════════════════════════════════════

def run_migrations_offline() -> None:
    """
    alembic upgrade --sql 모드 — DB 연결 없이 SQL 파일 생성.
    운영 환경 배포 시 DBA 검토용으로 사용.
    """
    url = get_sync_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ════════════════════════════════════════════════════════════
# 온라인 마이그레이션 (실제 DB 연결)
# ════════════════════════════════════════════════════════════

def run_migrations_online() -> None:
    """
    alembic upgrade head — 실제 DB에 마이그레이션 적용.
    """
    # alembic.ini의 sqlalchemy.url을 환경변수로 덮어씀
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_sync_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # 마이그레이션은 단일 연결로 충분
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,           # 컬럼 타입 변경 감지
            compare_server_default=True, # 서버 기본값 변경 감지
        )

        with context.begin_transaction():
            context.run_migrations()


# ════════════════════════════════════════════════════════════
# 진입점
# ════════════════════════════════════════════════════════════

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
