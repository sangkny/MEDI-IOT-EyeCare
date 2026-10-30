#!/bin/bash
# Phase 014 Docker verify — Docker-internal networking only; no host port publish.
set -euo pipefail
NET=ops014-net
ROOT=/mnt/c/Office_Automation/MEDI-IOT-EyeCare-ops-014
SHARED=/mnt/c/Tools/downloads/phase005-inspect/shared-libraries
PG=ops014-pg
APP=ops014-app
RUN=ops014-run

cleanup() {
  docker rm -f "$APP" "$RUN" "$PG" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker network inspect "$NET" >/dev/null 2>&1 || docker network create "$NET"
docker rm -f "$APP" "$RUN" "$PG" >/dev/null 2>&1 || true

docker run -d --name "$PG" --network "$NET" \
  -e POSTGRES_USER=eyecare -e POSTGRES_PASSWORD=ops014 -e POSTGRES_DB=eyecare \
  pgvector/pgvector:pg15

for _ in $(seq 1 60); do
  if docker exec "$PG" pg_isready -U eyecare >/dev/null 2>&1; then
    if docker exec "$PG" psql -U eyecare -d eyecare -c "SELECT 1" >/dev/null 2>&1; then
      break
    fi
  fi
  sleep 1
done
docker exec "$PG" psql -U eyecare -d eyecare -c "CREATE EXTENSION IF NOT EXISTS vector;"
# disposable pytest DB to avoid UniqueViolation on seeded codes
docker exec "$PG" psql -U eyecare -d postgres -c "DROP DATABASE IF EXISTS eyecare_pytest WITH (FORCE);"
docker exec "$PG" psql -U eyecare -d postgres -c "CREATE DATABASE eyecare_pytest;"
docker exec "$PG" psql -U eyecare -d eyecare_pytest -c "CREATE EXTENSION IF NOT EXISTS vector;"

# migrate both DBs
docker run --rm --name "$RUN" --network "$NET" \
  -v "$ROOT:/app" -v "$SHARED:/opt/shared-libraries:ro" -w /app \
  -e PYTHONPATH=/opt/shared-libraries:/app \
  -e DATABASE_URL=postgresql+asyncpg://eyecare:ops014@ops014-pg:5432/eyecare \
  -e EYECARE_PG_URL=postgresql://eyecare:ops014@ops014-pg:5432/eyecare \
  -e SECRET_KEY=synthetic-ops-014 \
  -e JWT_SECRET_KEY=synthetic-ops-014 \
  -e REDIS_URL= \
  python:3.12-slim \
  bash -lc 'pip install -q -r requirements.txt -r shared-libs-requirements.txt pytest aiosqlite && alembic upgrade head && DATABASE_URL=postgresql+asyncpg://eyecare:ops014@ops014-pg:5432/eyecare_pytest alembic upgrade head && python - <<"PY"
from sqlalchemy import create_engine, text
for db in ("eyecare", "eyecare_pytest"):
    eng = create_engine(f"postgresql://eyecare:ops014@ops014-pg:5432/{db}")
    with eng.connect() as c:
        v = c.execute(text("select version_num from alembic_version")).scalar()
        assert v == "medi012_questionnaire_engine", (db, v)
    print("MIGRATE_OK", db, v)
PY'

# unit + regression (use disposable pytest DB for EYECARE_PG_URL)
docker run --rm --name "$RUN" --network "$NET" \
  -v "$ROOT:/app" -v "$SHARED:/opt/shared-libraries:ro" -w /app \
  -e PYTHONPATH=/opt/shared-libraries:/app \
  -e DATABASE_URL=postgresql+asyncpg://eyecare:ops014@ops014-pg:5432/eyecare_pytest \
  -e EYECARE_PG_URL=postgresql://eyecare:ops014@ops014-pg:5432/eyecare_pytest \
  -e EYECARE_PG_ADMIN_URL=postgresql://eyecare:ops014@ops014-pg:5432/postgres \
  -e SECRET_KEY=synthetic-ops-014 \
  -e JWT_SECRET_KEY=synthetic-ops-014 \
  -e REDIS_URL= \
  python:3.12-slim \
  bash -lc 'apt-get update -qq && apt-get install -y -qq nodejs >/tmp/node.log && pip install -q -r requirements.txt -r shared-libs-requirements.txt pytest aiosqlite && pytest \
    tests/test_clinical_ops_page_js.py \
    tests/test_clinical_ops_ui.py \
    tests/test_questionnaire_page_js.py \
    tests/test_questionnaire_engine.py \
    tests/test_protocol_ecrf.py \
    tests/test_clinical_case_dashboard.py \
    tests/test_clinical_import.py \
    tests/test_clinical_data_lock.py \
    tests/test_clinical_query_quality.py \
    tests/test_clinical_support_models.py \
    tests/test_clinical_api.py \
    tests/test_observation_lifecycle.py \
    tests/test_multi_protocol_amd_013.py \
    -q --tb=line'

# boot app on docker-internal :8000 only (no -p)
docker run -d --name "$APP" --network "$NET" \
  -v "$ROOT:/app" -v "$SHARED:/opt/shared-libraries:ro" -w /app \
  -e PYTHONPATH=/opt/shared-libraries:/app \
  -e DATABASE_URL=postgresql+asyncpg://eyecare:ops014@ops014-pg:5432/eyecare \
  -e EYECARE_PG_URL=postgresql://eyecare:ops014@ops014-pg:5432/eyecare \
  -e SECRET_KEY=synthetic-ops-014 \
  -e JWT_SECRET_KEY=synthetic-ops-014 \
  -e REDIS_URL= \
  python:3.12-slim \
  bash -lc 'pip install -q -r requirements.txt -r shared-libs-requirements.txt && uvicorn main:app --host 0.0.0.0 --port 8000 --log-level warning'

for _ in $(seq 1 60); do
  if docker run --rm --network "$NET" curlimages/curl:8.5.0 -fsS "http://ops014-app:8000/health" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

docker run --rm --network "$NET" \
  -v "$ROOT:/app" -v "$SHARED:/opt/shared-libraries:ro" -w /app \
  -e PYTHONPATH=/opt/shared-libraries:/app \
  -e EYECARE_OPS_E2E_BASE=http://ops014-app:8000 \
  -e SECRET_KEY=synthetic-ops-014 \
  -e JWT_SECRET_KEY=synthetic-ops-014 \
  python:3.12-slim \
  bash -lc 'pip install -q -r requirements.txt -r shared-libs-requirements.txt pytest playwright httpx && python -m playwright install --with-deps chromium && PYTHONPATH=/opt/shared-libraries:/app pytest tests/test_clinical_ops_playwright_e2e.py tests/test_clinical_ops_browser_matrix.py -q --tb=line'

echo OPS014_DOCKER_VERIFY_OK
