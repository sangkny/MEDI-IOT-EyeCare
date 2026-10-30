#!/bin/bash
# Phase 014 completion validation — internal Docker only, no host port publish.
set -euo pipefail
NET=ops014c-net
ROOT=/mnt/c/Office_Automation/MEDI-IOT-EyeCare-ops-014
SHARED=/mnt/c/Tools/downloads/phase005-inspect/shared-libraries
ANALYZER_SRC=/mnt/c/Office_Automation/SVG-Analyzer
PG=ops014c-pg
APP=ops014c-app
IMG=python:3.12-slim
ANALYZER_IMG=ops014-svg-analyzer-arch:55f7105
PASS_LOG=/tmp/ops014c-results.txt
: > "$PASS_LOG"

cleanup() {
  docker rm -f "$APP" ops014c-run ops014c-run2 "$PG" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "=== REGISTRY ===" | tee -a "$PASS_LOG"
bash "$ROOT/scripts/_compare_port_registry.sh" | tee -a "$PASS_LOG"

docker network inspect "$NET" >/dev/null 2>&1 || docker network create "$NET"
docker rm -f "$APP" "$PG" >/dev/null 2>&1 || true

docker run -d --name "$PG" --network "$NET" \
  -e POSTGRES_USER=eyecare -e POSTGRES_PASSWORD=ops014c -e POSTGRES_DB=eyecare \
  pgvector/pgvector:pg15
for _ in $(seq 1 60); do
  docker exec "$PG" pg_isready -U eyecare >/dev/null 2>&1 && break
  sleep 1
done
docker exec "$PG" psql -U eyecare -d eyecare -c "CREATE EXTENSION IF NOT EXISTS vector;"
docker exec "$PG" psql -U eyecare -d postgres -c "DROP DATABASE IF EXISTS eyecare_pytest WITH (FORCE);"
docker exec "$PG" psql -U eyecare -d postgres -c "CREATE DATABASE eyecare_pytest;"
docker exec "$PG" psql -U eyecare -d eyecare_pytest -c "CREATE EXTENSION IF NOT EXISTS vector;"

migrate_db() {
  local db="$1"
  docker run --rm --name ops014c-run --network "$NET" \
    -v "$ROOT:/app" -v "$SHARED:/opt/shared-libraries:ro" -w /app \
    -e PYTHONPATH=/opt/shared-libraries:/app \
    -e DATABASE_URL="postgresql+asyncpg://eyecare:ops014c@ops014c-pg:5432/${db}" \
    -e SECRET_KEY=synthetic-ops-014c -e JWT_SECRET_KEY=synthetic-ops-014c -e REDIS_URL= \
    "$IMG" bash -lc 'pip install -q -r requirements.txt -r shared-libs-requirements.txt && alembic upgrade head && python - <<"PY"
from sqlalchemy import create_engine, text
import os
url=os.environ["DATABASE_URL"].replace("+asyncpg","")
eng=create_engine(url)
with eng.connect() as c:
    v=c.execute(text("select version_num from alembic_version")).scalar()
    assert v=="medi012_questionnaire_engine", v
print("MIGRATE_OK", os.environ["DATABASE_URL"].rsplit("/",1)[-1], v)
PY'
}

echo "=== MIGRATE ===" | tee -a "$PASS_LOG"
migrate_db eyecare | tee -a "$PASS_LOG"
migrate_db eyecare_pytest | tee -a "$PASS_LOG"

seed_once() {
  local label="$1"
  docker run --rm --name ops014c-run --network "$NET" \
    -v "$ROOT:/app" -v "$SHARED:/opt/shared-libraries:ro" -w /app \
    -e PYTHONPATH=/opt/shared-libraries:/app \
    -e EYECARE_PG_URL=postgresql://eyecare:ops014c@ops014c-pg:5432/eyecare \
    -e OPS014_SEED_MANIFEST=/app/docs/ops014-seed-manifest.json \
    -e SECRET_KEY=synthetic-ops-014c -e JWT_SECRET_KEY=synthetic-ops-014c -e REDIS_URL= \
    "$IMG" bash -lc 'pip install -q -r requirements.txt -r shared-libs-requirements.txt >/tmp/pip.log && python scripts/seed_ops014_synthetic.py'
  echo "SEED_${label}_OK" | tee -a "$PASS_LOG"
}

echo "=== SEED RUN1 ===" | tee -a "$PASS_LOG"
seed_once RUN1 | tee -a "$PASS_LOG"
echo "=== SEED RUN2 (repeatability / unique codes) ===" | tee -a "$PASS_LOG"
seed_once RUN2 | tee -a "$PASS_LOG"

echo "=== UNIT REGRESSION ===" | tee -a "$PASS_LOG"
docker run --rm --name ops014c-run --network "$NET" \
  -v "$ROOT:/app" -v "$SHARED:/opt/shared-libraries:ro" -w /app \
  -e PYTHONPATH=/opt/shared-libraries:/app \
  -e DATABASE_URL=postgresql+asyncpg://eyecare:ops014c@ops014c-pg:5432/eyecare_pytest \
  -e EYECARE_PG_URL=postgresql://eyecare:ops014c@ops014c-pg:5432/eyecare_pytest \
  -e EYECARE_PG_ADMIN_URL=postgresql://eyecare:ops014c@ops014c-pg:5432/postgres \
  -e SECRET_KEY=synthetic-ops-014c -e JWT_SECRET_KEY=synthetic-ops-014c -e REDIS_URL= \
  "$IMG" bash -lc 'apt-get update -qq && apt-get install -y -qq nodejs >/tmp/n.log && pip install -q -r requirements.txt -r shared-libs-requirements.txt pytest aiosqlite && pytest \
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
    -q --tb=line' | tee -a "$PASS_LOG"

echo "=== APP BOOT ===" | tee -a "$PASS_LOG"
docker run -d --name "$APP" --network "$NET" \
  -v "$ROOT:/app" -v "$SHARED:/opt/shared-libraries:ro" -w /app \
  -e PYTHONPATH=/opt/shared-libraries:/app \
  -e DATABASE_URL=postgresql+asyncpg://eyecare:ops014c@ops014c-pg:5432/eyecare \
  -e EYECARE_PG_URL=postgresql://eyecare:ops014c@ops014c-pg:5432/eyecare \
  -e SECRET_KEY=synthetic-ops-014c -e JWT_SECRET_KEY=synthetic-ops-014c -e REDIS_URL= \
  "$IMG" bash -lc 'pip install -q -r requirements.txt -r shared-libs-requirements.txt && uvicorn main:app --host 0.0.0.0 --port 8000 --log-level warning'

for _ in $(seq 1 90); do
  if docker run --rm --network "$NET" curlimages/curl:8.5.0 -fsS "http://ops014c-app:8000/health" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
docker run --rm --network "$NET" curlimages/curl:8.5.0 -fsS "http://ops014c-app:8000/clinical-ops" | head -c 120 | tee -a "$PASS_LOG"
echo | tee -a "$PASS_LOG"

echo "=== SEEDED PLAYWRIGHT E2E ===" | tee -a "$PASS_LOG"
docker run --rm --name ops014c-run --network "$NET" \
  -v "$ROOT:/app" -v "$SHARED:/opt/shared-libraries:ro" -w /app \
  -e PYTHONPATH=/opt/shared-libraries:/app \
  -e EYECARE_OPS_E2E_BASE=http://ops014c-app:8000 \
  -e EYECARE_OPS_SEED_MANIFEST=/app/docs/ops014-seed-manifest.json \
  -e SECRET_KEY=synthetic-ops-014c -e JWT_SECRET_KEY=synthetic-ops-014c \
  "$IMG" bash -lc 'pip install -q -r requirements.txt -r shared-libs-requirements.txt pytest playwright httpx && python -m playwright install --with-deps chromium && pytest tests/test_clinical_ops_seeded_playwright.py tests/test_clinical_ops_playwright_e2e.py -q --tb=short' | tee -a "$PASS_LOG"

echo "=== ANALYZER IMAGE ===" | tee -a "$PASS_LOG"
if ! docker image inspect "$ANALYZER_IMG" >/dev/null 2>&1; then
  docker build -t "$ANALYZER_IMG" -f - "$ANALYZER_SRC" <<'DOCKER'
FROM python:3.12-slim
WORKDIR /opt/svg-analyzer
COPY . .
RUN pip install -q -e .
ENTRYPOINT ["python", "-m", "svg_analyzer"]
DOCKER
fi
docker run --rm --name ops014c-run --network "$NET" \
  -v "$ROOT:/app" -v "$SHARED:/opt/shared-libraries:ro" -w /app \
  -e PYTHONPATH=/opt/shared-libraries:/app \
  "$IMG" bash -lc 'pip install -q -r requirements.txt -r shared-libs-requirements.txt >/tmp/p.log && python scripts/_export_arch_evidence_014.py' | tee -a "$PASS_LOG"

docker run --rm -v "$ROOT:/repo:ro" -v "$ROOT/docs:/out" -w /out "$ANALYZER_IMG" \
  architecture review /repo --evidence /repo/docs/architecture-evidence-014.json \
  -o /out/architecture-review-014.json | tee -a "$PASS_LOG"

if [ -f "$ROOT/docs/architecture-review-014.json" ]; then
  echo "ANALYZER_REPORT_OK" | tee -a "$PASS_LOG"
  docker run --rm -v "$ROOT/docs:/docs:ro" "$IMG" python - <<'PY' | tee -a "$PASS_LOG"
import json
from pathlib import Path
data=json.loads(Path("/docs/architecture-review-014.json").read_text(encoding="utf-8"))
findings=data.get("findings") or []
if isinstance(data.get("report"), dict):
    findings=data["report"].get("findings", findings)
print("MODULES", data.get("module_count") or len(data.get("modules") or []))
print("FINDINGS", len(findings) if isinstance(findings, list) else findings)
if isinstance(findings, list):
    for f in findings:
        if isinstance(f, dict):
            print("F", f.get("finding_id") or f.get("id"), f.get("module_id") or f.get("module"), f.get("check_id") or f.get("kind"), f.get("severity"))
PY
fi

echo "OPS014_COMPLETION_DONE" | tee -a "$PASS_LOG"
cp "$PASS_LOG" "$ROOT/docs/ops014-completion-docker-log.txt" || true
