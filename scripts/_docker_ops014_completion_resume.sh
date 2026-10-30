#!/bin/bash
# Resume after harness fix: migrate/seed/unit/e2e/analyzer. Internal Docker only.
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
  docker rm -f "$APP" ops014c-run "$PG" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker network inspect "$NET" >/dev/null 2>&1 || docker network create "$NET"
docker rm -f "$APP" "$PG" >/dev/null 2>&1 || true

docker run -d --name "$PG" --network "$NET" \
  -e POSTGRES_USER=eyecare -e POSTGRES_PASSWORD=ops014c -e POSTGRES_DB=eyecare \
  pgvector/pgvector:pg15
ready=0
for _ in $(seq 1 90); do
  if docker exec "$PG" pg_isready -U eyecare >/dev/null 2>&1; then
    if docker exec "$PG" psql -U eyecare -d eyecare -c "SELECT 1" >/dev/null 2>&1; then
      ready=1
      break
    fi
  fi
  sleep 1
done
if [ "$ready" != "1" ]; then
  docker logs "$PG" | tail -40
  exit 1
fi
docker exec "$PG" psql -U eyecare -d eyecare -c "CREATE EXTENSION IF NOT EXISTS vector;"
docker exec "$PG" psql -U eyecare -d postgres -c "DROP DATABASE IF EXISTS eyecare_pytest WITH (FORCE);"
docker exec "$PG" psql -U eyecare -d postgres -c "CREATE DATABASE eyecare_pytest;"
docker exec "$PG" psql -U eyecare -d eyecare_pytest -c "CREATE EXTENSION IF NOT EXISTS vector;"

for db in eyecare eyecare_pytest; do
  docker run --rm --name ops014c-run --network "$NET" \
    -v "$ROOT:/app" -v "$SHARED:/opt/shared-libraries:ro" -w /app \
    -e PYTHONPATH=/opt/shared-libraries:/app \
    -e DATABASE_URL="postgresql+asyncpg://eyecare:ops014c@ops014c-pg:5432/${db}" \
    -e SECRET_KEY=synthetic-ops-014c -e JWT_SECRET_KEY=synthetic-ops-014c -e REDIS_URL= \
    "$IMG" bash -lc 'pip install -q -r requirements.txt -r shared-libs-requirements.txt && alembic upgrade head'
  echo "MIGRATE_$db" | tee -a "$PASS_LOG"
done

docker run --rm --name ops014c-run --network "$NET" \
  -v "$ROOT:/app" -v "$SHARED:/opt/shared-libraries:ro" -w /app \
  -e PYTHONPATH=/opt/shared-libraries:/app \
  -e EYECARE_PG_URL=postgresql://eyecare:ops014c@ops014c-pg:5432/eyecare \
  -e OPS014_SEED_MANIFEST=/app/docs/ops014-seed-manifest.json \
  -e SECRET_KEY=synthetic-ops-014c -e JWT_SECRET_KEY=synthetic-ops-014c -e REDIS_URL= \
  "$IMG" bash -lc 'pip install -q -r requirements.txt -r shared-libs-requirements.txt >/tmp/p.log && python scripts/seed_ops014_synthetic.py' | tee -a "$PASS_LOG"
# second seed for collision-free repeatability
docker run --rm --name ops014c-run --network "$NET" \
  -v "$ROOT:/app" -v "$SHARED:/opt/shared-libraries:ro" -w /app \
  -e PYTHONPATH=/opt/shared-libraries:/app \
  -e EYECARE_PG_URL=postgresql://eyecare:ops014c@ops014c-pg:5432/eyecare \
  -e OPS014_SEED_MANIFEST=/app/docs/ops014-seed-manifest.json \
  -e SECRET_KEY=synthetic-ops-014c -e JWT_SECRET_KEY=synthetic-ops-014c -e REDIS_URL= \
  "$IMG" bash -lc 'pip install -q -r requirements.txt -r shared-libs-requirements.txt >/tmp/p.log && python scripts/seed_ops014_synthetic.py' | tee -a "$PASS_LOG"

echo "=== UNIT ===" | tee -a "$PASS_LOG"
docker run --rm --name ops014c-run --network "$NET" \
  -v "$ROOT:/app" -v "$SHARED:/opt/shared-libraries:ro" -w /app \
  -e PYTHONPATH=/opt/shared-libraries:/app \
  -e DATABASE_URL=postgresql+asyncpg://eyecare:ops014c@ops014c-pg:5432/eyecare_pytest \
  -e EYECARE_PG_URL=postgresql://eyecare:ops014c@ops014c-pg:5432/eyecare_pytest \
  -e EYECARE_PG_ADMIN_URL=postgresql://eyecare:ops014c@ops014c-pg:5432/postgres \
  -e SECRET_KEY=synthetic-ops-014c -e JWT_SECRET_KEY=synthetic-ops-014c -e REDIS_URL= \
  "$IMG" bash -lc 'apt-get update -qq && apt-get install -y -qq nodejs >/tmp/n.log && pip install -q -r requirements.txt -r shared-libs-requirements.txt pytest aiosqlite && pytest \
    tests/test_clinical_ops_page_js.py tests/test_clinical_ops_ui.py tests/test_questionnaire_page_js.py \
    tests/test_questionnaire_engine.py tests/test_protocol_ecrf.py tests/test_clinical_case_dashboard.py \
    tests/test_clinical_import.py tests/test_clinical_data_lock.py tests/test_clinical_query_quality.py \
    tests/test_clinical_support_models.py tests/test_clinical_api.py tests/test_observation_lifecycle.py \
    tests/test_multi_protocol_amd_013.py -q --tb=line' | tee -a "$PASS_LOG"

docker run -d --name "$APP" --network "$NET" \
  -v "$ROOT:/app" -v "$SHARED:/opt/shared-libraries:ro" -w /app \
  -e PYTHONPATH=/opt/shared-libraries:/app \
  -e DATABASE_URL=postgresql+asyncpg://eyecare:ops014c@ops014c-pg:5432/eyecare \
  -e SECRET_KEY=synthetic-ops-014c -e JWT_SECRET_KEY=synthetic-ops-014c -e REDIS_URL= \
  "$IMG" bash -lc 'pip install -q -r requirements.txt -r shared-libs-requirements.txt && uvicorn main:app --host 0.0.0.0 --port 8000 --log-level warning'
for _ in $(seq 1 90); do
  docker run --rm --network "$NET" curlimages/curl:8.5.0 -fsS "http://ops014c-app:8000/health" >/dev/null 2>&1 && break
  sleep 2
done

echo "=== E2E ===" | tee -a "$PASS_LOG"
docker run --rm --name ops014c-run --network "$NET" \
  -v "$ROOT:/app" -v "$SHARED:/opt/shared-libraries:ro" -w /app \
  -e PYTHONPATH=/opt/shared-libraries:/app \
  -e EYECARE_OPS_E2E_BASE=http://ops014c-app:8000 \
  -e EYECARE_OPS_SEED_MANIFEST=/app/docs/ops014-seed-manifest.json \
  -e SECRET_KEY=synthetic-ops-014c -e JWT_SECRET_KEY=synthetic-ops-014c \
  "$IMG" bash -lc 'pip install -q -r requirements.txt -r shared-libs-requirements.txt pytest playwright httpx && python -m playwright install --with-deps chromium && pytest tests/test_clinical_ops_seeded_playwright.py tests/test_clinical_ops_playwright_e2e.py -q --tb=short' | tee -a "$PASS_LOG"

echo "=== ANALYZER ===" | tee -a "$PASS_LOG"
docker run --rm --name ops014c-run -v "$ROOT:/app" -v "$SHARED:/opt/shared-libraries:ro" -w /app \
  -e PYTHONPATH=/opt/shared-libraries:/app "$IMG" \
  bash -lc 'pip install -q -r requirements.txt -r shared-libs-requirements.txt >/tmp/p.log && python scripts/_export_arch_evidence_014.py' | tee -a "$PASS_LOG"

if ! docker image inspect "$ANALYZER_IMG" >/dev/null 2>&1; then
  docker build -t "$ANALYZER_IMG" -f - "$ANALYZER_SRC" <<'DOCKER'
FROM python:3.12-slim
WORKDIR /opt/svg-analyzer
COPY . .
RUN pip install -q -e .
ENTRYPOINT ["python", "-m", "svg_analyzer"]
DOCKER
fi

docker run --rm -v "$ROOT:/repo:ro" -v "$ROOT/docs:/out" -w /tmp "$ANALYZER_IMG" \
  architecture review /repo --evidence /repo/docs/architecture-evidence-014.json \
  -o /out/architecture-review-014.json | tee -a "$PASS_LOG"

docker run --rm -v "$ROOT/docs:/docs:ro" "$IMG" python - <<'PY' | tee -a "$PASS_LOG"
import json
from pathlib import Path
p=Path('/docs/architecture-review-014.json')
print('REPORT_EXISTS', p.is_file())
if p.is_file():
  data=json.loads(p.read_text(encoding='utf-8'))
  findings=data.get('findings') or []
  print('KEYS', sorted(data.keys())[:30])
  print('FINDINGS', len(findings) if isinstance(findings, list) else type(findings))
  if isinstance(findings, list):
    for f in findings:
      if isinstance(f, dict):
        print('F', f.get('finding_id') or f.get('id'), f.get('module_id'), f.get('check_id'), f.get('severity'))
PY

echo "OPS014_COMPLETION_DONE" | tee -a "$PASS_LOG"
cp "$PASS_LOG" "$ROOT/docs/ops014-completion-docker-log.txt"
