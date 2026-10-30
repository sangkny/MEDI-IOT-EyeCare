"""테스트 전용 PostgreSQL 격리 헬퍼.

이미 시드된 공유 DB를 재사용하면 study.code UniqueViolation 이 날 수 있다.
프로덕션 임상 레코드를 삭제하지 않는다. 일회용 DB 또는 고유 네임스페이스만 사용한다.
"""
from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, text


def unique_study_code(prefix: str = "T014") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"


def disposable_database_url(base_url: str | None = None, *, name_prefix: str = "eyecare_ops014_") -> str | None:
    """EYECARE_PG_ADMIN_URL 이 있으면 일회용 DB를 만들고 URL을 반환한다.

    예: postgresql://eyecare:pw@pg:5432/postgres
    없으면 None (호출측 skip).
    """
    admin = base_url or os.environ.get("EYECARE_PG_ADMIN_URL", "")
    if not admin.startswith("postgresql"):
        return None
    db_name = f"{name_prefix}{uuid.uuid4().hex[:8]}"
    engine = create_engine(admin, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    engine.dispose()
    # rewrite path
    if "/postgres" in admin:
        return admin.rsplit("/postgres", 1)[0] + f"/{db_name}"
    return admin.rstrip("/") + f"/{db_name}"


@contextmanager
def disposable_postgres(admin_url: str | None = None) -> Iterator[str]:
    url = disposable_database_url(admin_url)
    if url is None:
        raise RuntimeError("EYECARE_PG_ADMIN_URL required for disposable postgres")
    db_name = url.rsplit("/", 1)[-1]
    admin = admin_url or os.environ["EYECARE_PG_ADMIN_URL"]
    try:
        yield url
    finally:
        engine = create_engine(admin, isolation_level="AUTOCOMMIT")
        with engine.connect() as conn:
            conn.execute(text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = '{db_name}' AND pid <> pg_backend_pid()"
            ))
            conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
        engine.dispose()
