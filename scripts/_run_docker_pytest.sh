#!/bin/bash
set -euo pipefail
docker exec \
  -e PYTHONPATH=/opt/shared-libraries:/app \
  -e DATABASE_URL=postgresql+asyncpg://eyecare:ecrf012b@ecrf012b-pg:5432/eyecare \
  -e EYECARE_PG_URL=postgresql://eyecare:ecrf012b@ecrf012b-pg:5432/eyecare_pytest \
  -e SECRET_KEY=synthetic-ecrf-012b \
  -e REDIS_URL= \
  -w /app ecrf012b-app \
  pytest \
  tests/test_questionnaire_engine.py \
  tests/test_protocol_ecrf.py \
  tests/test_clinical_case_dashboard.py \
  tests/test_clinical_import.py \
  tests/test_clinical_data_lock.py \
  tests/test_clinical_query_quality.py \
  tests/test_clinical_support_models.py \
  tests/test_clinical_api.py \
  tests/test_observation_lifecycle.py \
  -q --tb=line
echo DOCKER_PYTEST_DONE
