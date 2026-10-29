#!/bin/bash
set -euo pipefail
NET=amd013integ-net
ROOT=/mnt/c/Office_Automation/MEDI-IOT-EyeCare-amd013-integ
SHARED=/mnt/c/Tools/downloads/phase005-inspect/shared-libraries
docker network inspect "$NET" >/dev/null 2>&1 || docker network create "$NET"
docker rm -f amd013integ-pg amd013integ-run >/dev/null 2>&1 || true
sleep 2
docker run -d --name amd013integ-pg --network "$NET" \
  -e POSTGRES_USER=eyecare -e POSTGRES_PASSWORD=amd013integ -e POSTGRES_DB=eyecare \
  pgvector/pgvector:pg15
for _ in $(seq 1 60); do
  if docker exec amd013integ-pg pg_isready -U eyecare >/dev/null 2>&1; then
    docker exec amd013integ-pg psql -U eyecare -d eyecare -c "SELECT 1" >/dev/null 2>&1 && break
  fi
  sleep 1
done
docker exec amd013integ-pg psql -U eyecare -d eyecare -c "CREATE EXTENSION IF NOT EXISTS vector;"
docker run --rm --name amd013integ-run --network "$NET" \
  -v "$ROOT:/app" -v "$SHARED:/opt/shared-libraries:ro" -w /app \
  -e PYTHONPATH=/opt/shared-libraries:/app \
  -e DATABASE_URL=postgresql+asyncpg://eyecare:amd013integ@amd013integ-pg:5432/eyecare \
  -e EYECARE_PG_URL=postgresql://eyecare:amd013integ@amd013integ-pg:5432/eyecare \
  -e SECRET_KEY=synthetic-amd-013-integ \
  -e REDIS_URL= \
  python:3.12-slim \
  bash -lc 'pip install -q -r requirements.txt -r shared-libs-requirements.txt pytest aiosqlite && alembic upgrade head && python - <<'"'"'PY'"'"'
from sqlalchemy import create_engine, text
e=create_engine("postgresql://eyecare:amd013integ@amd013integ-pg:5432/eyecare")
with e.connect() as c:
    v=c.execute(text("select version_num from alembic_version")).scalar()
    assert v=="medi012_questionnaire_engine", v
    print("MIGRATE", v)
PY
pytest tests/test_amd_protocol_findings.py tests/test_multi_protocol_amd_013.py tests/test_protocol_ecrf.py tests/test_questionnaire_engine.py -q --tb=line'
EC=$?
docker rm -f amd013integ-pg >/dev/null 2>&1 || true
docker network rm "$NET" >/dev/null 2>&1 || true
exit $EC
