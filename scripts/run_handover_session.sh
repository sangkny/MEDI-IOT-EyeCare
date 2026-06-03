#!/bin/bash
# 2026-06-03 handover session: docker + tests + gradcam
set -euo pipefail
PROJECTS=/mnt/e/Office_Automation/idea-collection/projects
MEDI=$PROJECTS/MEDI-IOT-EyeCare

echo "=== STEP 1 Docker ==="
cd "$PROJECTS"
[ -f .env.local ] && set -a && source .env.local && set +a
docker compose -f docker-compose.dev.yml down
docker compose -f docker-compose.dev.yml up -d
sleep 35
docker ps --format 'table {{.Names}}\t{{.Ports}}' | sort
echo "--- health ---"
curl -sf http://localhost:8001/health | python3 -m json.tool || echo "MEDI fail"
curl -sf http://localhost:8003/health | python3 -m json.tool || echo "CoOps fail"

echo "=== STEP 2 MEDI unit (docker) ==="
docker exec medi-iot-api-dev bash -c \
  "python -m pytest tests/ -q -m unit --tb=short 2>&1 | tail -8"

echo "=== STEP 5 GradCAM ==="
bash "$MEDI/scripts/test_gradcam_e2e.sh" 2>&1 | tail -25
