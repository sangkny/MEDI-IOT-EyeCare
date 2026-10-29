#!/bin/bash
set -euo pipefail
ROOT=/mnt/c/Office_Automation/MEDI-IOT-EyeCare-ecrf-012
SHARED=/mnt/c/Tools/downloads/phase005-inspect/shared-libraries
NET=ecrf012b-net
docker network inspect "$NET" >/dev/null 2>&1 || docker network create "$NET"
docker rm -f ecrf012b-app ecrf012b-pg >/dev/null 2>&1 || true
# keep redis if healthy
if ! docker ps --format '{{.Names}}' | grep -qx ecrf012b-redis; then
  docker rm -f ecrf012b-redis >/dev/null 2>&1 || true
  docker run -d --name ecrf012b-redis --network "$NET" redis:7-alpine
fi
docker run -d --name ecrf012b-pg --network "$NET" \
  -e POSTGRES_USER=eyecare -e POSTGRES_PASSWORD=ecrf012b -e POSTGRES_DB=eyecare \
  pgvector/pgvector:pg15
for _ in $(seq 1 40); do
  if docker exec ecrf012b-pg pg_isready -U eyecare >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
docker exec ecrf012b-pg pg_isready -U eyecare
docker run -d --name ecrf012b-app --network "$NET" \
  -v "$ROOT:/app" \
  -v "$SHARED:/opt/shared-libraries:ro" \
  -w /app \
  python:3.12-slim \
  bash /app/scripts/_docker_app_boot.sh
echo RELAUNCHED2
