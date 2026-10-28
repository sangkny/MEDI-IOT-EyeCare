#!/bin/bash
set -euo pipefail
NET=ecrf012pub-net
ROOT=/mnt/c/Office_Automation/MEDI-IOT-EyeCare-ecrf-012
SHARED=/mnt/c/Tools/downloads/phase005-inspect/shared-libraries
docker network inspect "$NET" >/dev/null 2>&1 || docker network create "$NET"
docker rm -f ecrf012pub-pg ecrf012pub-run >/dev/null 2>&1 || true
sleep 2
docker run -d --name ecrf012pub-pg --network "$NET" \
  -e POSTGRES_USER=eyecare -e POSTGRES_PASSWORD=ecrf012pub -e POSTGRES_DB=eyecare \
  pgvector/pgvector:pg15
for _ in $(seq 1 60); do
  if docker exec ecrf012pub-pg pg_isready -U eyecare >/dev/null 2>&1; then
    if docker exec ecrf012pub-pg psql -U eyecare -d eyecare -c "SELECT 1" >/dev/null 2>&1; then
      break
    fi
  fi
  sleep 1
done
docker exec ecrf012pub-pg psql -U eyecare -d eyecare -c "CREATE EXTENSION IF NOT EXISTS vector;"
docker run --rm --name ecrf012pub-run --network "$NET" \
  -v "$ROOT:/app" -v "$SHARED:/opt/shared-libraries:ro" -w /app \
  -e PYTHONPATH=/opt/shared-libraries:/app \
  -e DATABASE_URL=postgresql+asyncpg://eyecare:ecrf012pub@ecrf012pub-pg:5432/eyecare \
  -e EYECARE_PG_URL=postgresql://eyecare:ecrf012pub@ecrf012pub-pg:5432/eyecare \
  -e SECRET_KEY=synthetic-ecrf-012-publish \
  -e REDIS_URL= \
  python:3.12-slim \
  bash -lc 'pip install -q -r requirements.txt -r shared-libs-requirements.txt pytest aiosqlite && alembic upgrade head && python - <<'"'"'PY'"'"'
from sqlalchemy import create_engine, text
e=create_engine("postgresql://eyecare:ecrf012pub@ecrf012pub-pg:5432/eyecare")
with e.connect() as c:
    v=c.execute(text("select version_num from alembic_version")).scalar()
    assert v=="medi012_questionnaire_engine", v
    print("MIGRATE", v)
PY
pytest tests/test_questionnaire_engine.py tests/test_protocol_ecrf.py tests/test_clinical_case_dashboard.py tests/test_clinical_import.py tests/test_clinical_data_lock.py tests/test_clinical_query_quality.py tests/test_clinical_support_models.py tests/test_observation_lifecycle.py -q --tb=line'
EC=$?
docker rm -f ecrf012pub-pg >/dev/null 2>&1 || true
docker network rm "$NET" >/dev/null 2>&1 || true
exit $EC
