#!/bin/bash
set -euo pipefail
pip install -q alembic==1.14.0 sqlalchemy==2.0.36 psycopg2-binary==2.9.12 asyncpg==0.30.0 pydantic==2.10.3 pydantic-settings==2.6.1 fastapi==0.115.6 python-jose==3.3.0 pgvector==0.4.2
alembic upgrade head
echo MIGRATE_OK
python - <<'PY'
from sqlalchemy import create_engine, text
engine = create_engine("postgresql://eyecare:ecrf012a@ecrf012a-pg:5432/eyecare")
with engine.begin() as conn:
    print(conn.execute(text("select version_num from alembic_version")).scalar())
    tables = {row[0] for row in conn.execute(text("select tablename from pg_tables where schemaname='public'"))}
    assert "questionnaire_score_results" in tables
    assert "improvement_findings" in tables
    print("TABLES_OK")
PY
