#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq gcc libpq-dev >/tmp/apt.log
pip install -q -r requirements.txt -r shared-libs-requirements.txt pytest
export DATABASE_URL=postgresql+asyncpg://eyecare:ecrf012b@ecrf012b-pg:5432/eyecare
export EYECARE_PG_URL=postgresql://eyecare:ecrf012b@ecrf012b-pg:5432/eyecare
export REDIS_URL=redis://ecrf012b-redis:6379/0
export SECRET_KEY=synthetic-ecrf-012b
export PYTHONPATH=/opt/shared-libraries:/app
export PYTHONUNBUFFERED=1
python - <<'PY'
from sqlalchemy import create_engine, text
engine = create_engine("postgresql://eyecare:ecrf012b@ecrf012b-pg:5432/eyecare")
with engine.begin() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
print("VECTOR_OK")
PY
alembic upgrade head
python - <<'PY'
from sqlalchemy import create_engine, text
engine = create_engine("postgresql://eyecare:ecrf012b@ecrf012b-pg:5432/eyecare")
with engine.connect() as conn:
    version = conn.execute(text("select version_num from alembic_version")).scalar()
    assert version == "medi012_questionnaire_engine", version
    names = {row[0] for row in conn.execute(text("select tablename from pg_tables where schemaname='public'"))}
    assert "questionnaire_score_results" in names
    assert "improvement_findings" in names
    assert "audit_event_chains" in names
    parents = list(conn.execute(text(
        "select version_num from alembic_version"
    )))
print("MIGRATE", version)
PY
uvicorn main:app --host 127.0.0.1 --port 8000 --log-level warning
