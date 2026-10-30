#!/bin/bash
# Resume E2E only after unit suite already passed (Docker-internal, no host ports).
set -euo pipefail
NET=ops014-net
ROOT=/mnt/c/Office_Automation/MEDI-IOT-EyeCare-ops-014
SHARED=/mnt/c/Tools/downloads/phase005-inspect/shared-libraries
PG=ops014-pg
APP=ops014-app

cleanup() {
  docker rm -f "$APP" "$PG" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker network inspect "$NET" >/dev/null 2>&1 || docker network create "$NET"
docker rm -f "$APP" "$PG" >/dev/null 2>&1 || true

docker run -d --name "$PG" --network "$NET" \
  -e POSTGRES_USER=eyecare -e POSTGRES_PASSWORD=ops014 -e POSTGRES_DB=eyecare \
  pgvector/pgvector:pg15
for _ in $(seq 1 60); do
  docker exec "$PG" pg_isready -U eyecare >/dev/null 2>&1 && break
  sleep 1
done
docker exec "$PG" psql -U eyecare -d eyecare -c "CREATE EXTENSION IF NOT EXISTS vector;"

docker run --rm --network "$NET" \
  -v "$ROOT:/app" -v "$SHARED:/opt/shared-libraries:ro" -w /app \
  -e PYTHONPATH=/opt/shared-libraries:/app \
  -e DATABASE_URL=postgresql+asyncpg://eyecare:ops014@ops014-pg:5432/eyecare \
  -e SECRET_KEY=synthetic-ops-014 -e JWT_SECRET_KEY=synthetic-ops-014 -e REDIS_URL= \
  python:3.12-slim \
  bash -lc 'pip install -q -r requirements.txt -r shared-libs-requirements.txt && alembic upgrade head'

docker run -d --name "$APP" --network "$NET" \
  -v "$ROOT:/app" -v "$SHARED:/opt/shared-libraries:ro" -w /app \
  -e PYTHONPATH=/opt/shared-libraries:/app \
  -e DATABASE_URL=postgresql+asyncpg://eyecare:ops014@ops014-pg:5432/eyecare \
  -e SECRET_KEY=synthetic-ops-014 -e JWT_SECRET_KEY=synthetic-ops-014 -e REDIS_URL= \
  python:3.12-slim \
  bash -lc 'pip install -q -r requirements.txt -r shared-libs-requirements.txt && uvicorn main:app --host 0.0.0.0 --port 8000 --log-level warning'

for _ in $(seq 1 90); do
  if docker run --rm --network "$NET" curlimages/curl:8.5.0 -fsS "http://ops014-app:8000/health" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
docker run --rm --network "$NET" curlimages/curl:8.5.0 -fsS "http://ops014-app:8000/clinical-ops" | head -c 200

docker run --rm --network "$NET" \
  -v "$ROOT:/app" -v "$SHARED:/opt/shared-libraries:ro" -w /app \
  -e PYTHONPATH=/opt/shared-libraries:/app \
  -e EYECARE_OPS_E2E_BASE=http://ops014-app:8000 \
  -e SECRET_KEY=synthetic-ops-014 -e JWT_SECRET_KEY=synthetic-ops-014 \
  python:3.12-slim \
  bash -lc 'pip install -q -r requirements.txt -r shared-libs-requirements.txt pytest playwright httpx && python -m playwright install --with-deps chromium && pytest tests/test_clinical_ops_playwright_e2e.py tests/test_clinical_ops_browser_matrix.py -q --tb=line'

echo OPS014_E2E_OK
