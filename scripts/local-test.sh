#!/usr/bin/env bash
# local-test.sh — 로컬 Docker 스택에서 전체 pytest (integration·ONNX·LLM 포함)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE="${ROOT}/../docker-compose.dev.yml"

echo "=== 로컬 전체 테스트 ==="
echo "Docker 스택 기동: ${COMPOSE}"
docker compose -f "${COMPOSE}" up -d postgres redis medi-iot-api
echo "서비스 준비 대기 (15s)..."
sleep 15

echo "전체 pytest (integration·unit, 장시간 E2E 제외)..."
docker compose -f "${COMPOSE}" exec -T medi-iot-api \
  python -m pytest tests/ -q \
  --ignore=tests/test_e2e_week4_full_flow.py \
  --tb=short

if [[ -x "${ROOT}/scripts/medi-r4-ml-d4-smoke.sh" ]]; then
  echo "Harness 스모크..."
  docker compose -f "${COMPOSE}" exec -T medi-iot-api \
    bash scripts/medi-r4-ml-d4-smoke.sh
fi

echo "=== 로컬 전체 테스트 완료 ==="
