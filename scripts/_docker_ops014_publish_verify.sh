#!/bin/bash
# Final release-boundary verify before Phase 014 push. Internal Docker only.
set -euo pipefail
NET=ops014p-net
ROOT=/mnt/c/Office_Automation/MEDI-IOT-EyeCare-ops-014
SHARED=/mnt/c/Tools/downloads/phase005-inspect/shared-libraries
PG=ops014p-pg
APP=ops014p-app
IMG=python:3.12-slim
PASS_LOG=/tmp/ops014p-results.txt
: > "$PASS_LOG"

cleanup() {
  docker rm -f "$APP" ops014p-run "$PG" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT

bash "$ROOT/scripts/_compare_port_registry_brief.sh" | tee -a "$PASS_LOG"

docker network create "$NET"
docker run -d --name "$PG" --network "$NET" \
  -e POSTGRES_USER=eyecare -e POSTGRES_PASSWORD=ops014p -e POSTGRES_DB=eyecare \
  pgvector/pgvector:pg15
ready=0
for _ in $(seq 1 90); do
  if docker exec "$PG" pg_isready -U eyecare >/dev/null 2>&1 \
    && docker exec "$PG" psql -U eyecare -d eyecare -c "SELECT 1" >/dev/null 2>&1; then
    ready=1; break
  fi
  sleep 1
done
[ "$ready" = "1" ]
docker exec "$PG" psql -U eyecare -d eyecare -c "CREATE EXTENSION IF NOT EXISTS vector;"
docker exec "$PG" psql -U eyecare -d postgres -c "CREATE DATABASE eyecare_pytest;"
docker exec "$PG" psql -U eyecare -d eyecare_pytest -c "CREATE EXTENSION IF NOT EXISTS vector;"

for db in eyecare eyecare_pytest; do
  docker run --rm --name ops014p-run --network "$NET" \
    -v "$ROOT:/app" -v "$SHARED:/opt/shared-libraries:ro" -w /app \
    -e PYTHONPATH=/opt/shared-libraries:/app \
    -e DATABASE_URL="postgresql+asyncpg://eyecare:ops014p@ops014p-pg:5432/${db}" \
    -e SECRET_KEY=synthetic-ops-014p -e JWT_SECRET_KEY=synthetic-ops-014p -e REDIS_URL= \
    "$IMG" bash -lc 'pip install -q -r requirements.txt -r shared-libs-requirements.txt && alembic upgrade head && python - <<"PY"
from sqlalchemy import create_engine, text
import os
u=os.environ["DATABASE_URL"].replace("+asyncpg","")
with create_engine(u).connect() as c:
    v=c.execute(text("select version_num from alembic_version")).scalar()
assert v=="medi012_questionnaire_engine", v
print("MIGRATE_OK", v)
PY'
done | tee -a "$PASS_LOG"

docker run --rm --name ops014p-run --network "$NET" \
  -v "$ROOT:/app" -v "$SHARED:/opt/shared-libraries:ro" -w /app \
  -e PYTHONPATH=/opt/shared-libraries:/app \
  -e EYECARE_PG_URL=postgresql://eyecare:ops014p@ops014p-pg:5432/eyecare \
  -e OPS014_SEED_MANIFEST=/app/docs/ops014-seed-manifest.json \
  -e SECRET_KEY=synthetic-ops-014p -e JWT_SECRET_KEY=synthetic-ops-014p -e REDIS_URL= \
  "$IMG" bash -lc 'pip install -q -r requirements.txt -r shared-libs-requirements.txt >/tmp/p.log && python scripts/seed_ops014_synthetic.py && python scripts/seed_ops014_synthetic.py' | tee -a "$PASS_LOG"

echo "=== UNIT ===" | tee -a "$PASS_LOG"
docker run --rm --name ops014p-run --network "$NET" \
  -v "$ROOT:/app" -v "$SHARED:/opt/shared-libraries:ro" -w /app \
  -e PYTHONPATH=/opt/shared-libraries:/app \
  -e DATABASE_URL=postgresql+asyncpg://eyecare:ops014p@ops014p-pg:5432/eyecare_pytest \
  -e EYECARE_PG_URL=postgresql://eyecare:ops014p@ops014p-pg:5432/eyecare_pytest \
  -e EYECARE_PG_ADMIN_URL=postgresql://eyecare:ops014p@ops014p-pg:5432/postgres \
  -e SECRET_KEY=synthetic-ops-014p -e JWT_SECRET_KEY=synthetic-ops-014p -e REDIS_URL= \
  "$IMG" bash -lc 'apt-get update -qq && apt-get install -y -qq nodejs >/tmp/n.log && pip install -q -r requirements.txt -r shared-libs-requirements.txt pytest aiosqlite && pytest \
    tests/test_clinical_ops_page_js.py tests/test_clinical_ops_ui.py tests/test_questionnaire_page_js.py \
    tests/test_questionnaire_engine.py tests/test_protocol_ecrf.py tests/test_clinical_case_dashboard.py \
    tests/test_clinical_import.py tests/test_clinical_data_lock.py tests/test_clinical_query_quality.py \
    tests/test_clinical_support_models.py tests/test_clinical_api.py tests/test_observation_lifecycle.py \
    tests/test_multi_protocol_amd_013.py -q --tb=line' | tee -a "$PASS_LOG"

docker run -d --name "$APP" --network "$NET" \
  -v "$ROOT:/app" -v "$SHARED:/opt/shared-libraries:ro" -w /app \
  -e PYTHONPATH=/opt/shared-libraries:/app \
  -e DATABASE_URL=postgresql+asyncpg://eyecare:ops014p@ops014p-pg:5432/eyecare \
  -e SECRET_KEY=synthetic-ops-014p -e JWT_SECRET_KEY=synthetic-ops-014p -e REDIS_URL= \
  "$IMG" bash -lc 'pip install -q -r requirements.txt -r shared-libs-requirements.txt && uvicorn main:app --host 0.0.0.0 --port 8000 --log-level warning'
for _ in $(seq 1 90); do
  docker run --rm --network "$NET" curlimages/curl:8.5.0 -fsS "http://ops014p-app:8000/health" >/dev/null 2>&1 && break
  sleep 2
done

echo "=== E2E ===" | tee -a "$PASS_LOG"
docker run --rm --name ops014p-run --network "$NET" \
  -v "$ROOT:/app" -v "$SHARED:/opt/shared-libraries:ro" -w /app \
  -e PYTHONPATH=/opt/shared-libraries:/app \
  -e EYECARE_OPS_E2E_BASE=http://ops014p-app:8000 \
  -e EYECARE_OPS_SEED_MANIFEST=/app/docs/ops014-seed-manifest.json \
  -e SECRET_KEY=synthetic-ops-014p -e JWT_SECRET_KEY=synthetic-ops-014p \
  "$IMG" bash -lc 'pip install -q -r requirements.txt -r shared-libs-requirements.txt pytest playwright httpx && python -m playwright install --with-deps chromium && pytest tests/test_clinical_ops_seeded_playwright.py tests/test_clinical_ops_playwright_e2e.py -q --tb=line' | tee -a "$PASS_LOG"

echo "=== EVIDENCE ===" | tee -a "$PASS_LOG"
docker run --rm --name ops014p-run -v "$ROOT:/app" -v "$SHARED:/opt/shared-libraries:ro" -w /app \
  -e PYTHONPATH=/opt/shared-libraries:/app "$IMG" \
  bash -lc 'pip install -q -r requirements.txt -r shared-libs-requirements.txt >/tmp/p.log && python scripts/_export_arch_evidence_014.py' | tee -a "$PASS_LOG"

echo "OPS014_PUBLISH_VERIFY_OK" | tee -a "$PASS_LOG"
cp "$PASS_LOG" "$ROOT/docs/ops014-publish-verify-log.txt"
