#!/bin/bash
set -euo pipefail
pip install -q -r requirements.txt -r shared-libs-requirements.txt
export DATABASE_URL=postgresql+asyncpg://eyecare:ecrf012b@ecrf012b-pg:5432/eyecare
export EYECARE_PG_URL=postgresql://eyecare:ecrf012b@ecrf012b-pg:5432/eyecare
export REDIS_URL=redis://ecrf012b-redis:6379/0
export SECRET_KEY=synthetic-ecrf-012b
export PYTHONPATH=/opt/shared-libraries:/app
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
print("MIGRATE", version)
PY
uvicorn main:app --host 127.0.0.1 --port 8000 --log-level warning &
APP_PID=$!
trap 'kill $APP_PID 2>/dev/null || true' EXIT
for i in $(seq 1 40); do
  if python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"; then
    break
  fi
  sleep 1
done
python /app/scripts/_jwt_questionnaire_flow.py
pytest tests/test_questionnaire_engine.py tests/test_protocol_ecrf.py tests/test_clinical_case_dashboard.py tests/test_clinical_import.py tests/test_clinical_data_lock.py tests/test_clinical_query_quality.py tests/test_clinical_support_models.py tests/test_clinical_api.py tests/test_observation_lifecycle.py -q --tb=line
echo DOCKER_VERIFY_OK
