#!/bin/bash
set -euo pipefail
docker exec ecrf012b-pg psql -U eyecare -d postgres -c "DROP DATABASE IF EXISTS eyecare_pytest WITH (FORCE);"
docker exec ecrf012b-pg psql -U eyecare -d postgres -c "CREATE DATABASE eyecare_pytest;"
docker exec ecrf012b-pg psql -U eyecare -d eyecare_pytest -c "CREATE EXTENSION IF NOT EXISTS vector;"
docker exec \
  -e PYTHONPATH=/opt/shared-libraries:/app \
  -e DATABASE_URL=postgresql+asyncpg://eyecare:ecrf012b@ecrf012b-pg:5432/eyecare_pytest \
  -e EYECARE_PG_URL=postgresql://eyecare:ecrf012b@ecrf012b-pg:5432/eyecare_pytest \
  -w /app ecrf012b-app alembic upgrade head
docker exec ecrf012b-pg psql -U eyecare -d eyecare_pytest -tAc "select version_num from alembic_version"
