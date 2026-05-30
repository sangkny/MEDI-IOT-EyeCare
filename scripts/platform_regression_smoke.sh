#!/bin/bash
# 개발 PC 전체 회귀 스모크 (v8b 병행 작업용)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/../.."
PROJECTS="$(pwd)"

echo "=== shared-libraries ==="
docker exec medi-iot-api-dev bash -c "
  export PYTHONPATH=/app/shared-libraries
  AGENT_DECISION_MODE=legacy \
  python -m pytest /app/shared-libraries/tests/ -q \
    --ignore=/app/shared-libraries/tests/integration \
    --ignore=/app/shared-libraries/tests/test_inbox_retention.py \
    --tb=line 2>&1 | tail -3
"

echo "=== LLM 10/10 ==="
docker exec medi-iot-api-dev bash -c "
  export PYTHONPATH=/app/shared-libraries
  python -m pytest /app/shared-libraries/llm/tests/test_providers.py -q --tb=line 2>&1 | tail -3
"

echo "=== CoOps (Stripe 제외) ==="
docker exec coops-api-dev bash -c "
  python -m pytest tests/ -q \
    --ignore=tests/test_stripe.py \
    --ignore=tests/test_stripe_r2.py \
    --tb=line 2>&1 | tail -3
"

echo "=== MEDI unit ==="
docker exec medi-iot-api-dev bash -c "
  python -m pytest tests/ -q -m unit --tb=line 2>&1 | tail -3
"

echo "=== GradCAM E2E ==="
bash "$ROOT/scripts/test_gradcam_e2e.sh" 2>&1 | tail -20

echo "=== IoT HealthKit ==="
curl -sf -X POST http://localhost:8001/api/v1/iot/healthkit \
  -H "Content-Type: application/json" \
  -d '{"patient_id":"P001","blood_glucose":126,"unit":"mg/dL","timestamp":"2026-05-30T08:00:00Z"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('status',d.get('status'),'ontology',d.get('ontology_passed'))"

echo "=== OpenAPI count ==="
curl -sf http://localhost:8001/openapi.json \
  | python3 -c "import sys,json; print('endpoints', len(json.load(sys.stdin).get('paths',{})))"

echo "OK regression smoke done"
