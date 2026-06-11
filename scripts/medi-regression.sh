#!/usr/bin/env bash
# =============================================================
# 파일명: medi-regression.sh
# 목적: MEDI-IOT 전체 회귀 테스트 — unit/smoke/slow/full 모드
# 히스토리:
#   2026-06-12 - LLM mock + .env.test (e4b only), slow 모드 분리
#   2026-06-11 - unit/smoke/e2e/full 모드 정리 + pytest 마커 연동
#   2026-06-11 - v4 단일모델 → v10c 5질환 멀티모델 확장
# =============================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODE="${1:-unit}"
COMPOSE="${COMPOSE_FILE:-../docker-compose.dev.yml}"
SERVICE="${MEDI_SERVICE:-medi-iot-api-dev}"
ENV_FILE="${ENV_FILE:-.env.test}"

_exec_env() {
  local mode="${1:-mock}"
  shift
  local -a extra=()
  if [ -f "$ENV_FILE" ]; then
    extra+=(--env-file "$ENV_FILE")
  fi
  if [ "$mode" = "mock" ]; then
    extra+=(-e AGENT_FOUR_AGENT_MOCK=1 -e PYTEST_LLM_MOCK=1)
  fi
  docker compose -f "$COMPOSE" exec -T "${extra[@]}" "$SERVICE" python -m pytest "$@"
}

case "$MODE" in
  unit)
    echo "=== MEDI regression: unit (~2min, LLM mock, LM Studio 불필요) ==="
    _exec_env mock tests/ -q --tb=short -m "unit" --ignore=tests/test_e2e.py
    ;;
  smoke)
    echo "=== MEDI regression: smoke (~5min, API + LLM mock) ==="
    _exec_env mock tests/ -q --tb=short -m "unit or (integration and not slow and not requires_llm)" --ignore=tests/test_e2e.py
    ;;
  slow)
    echo "=== MEDI regression: slow (~30min, LM Studio e4b, .env.test) ==="
    _exec_env live tests/ -q --tb=short -m "slow or requires_llm"
    ;;
  full)
    echo "=== MEDI regression: full (~60min, not slow) ==="
    _exec_env mock tests/ -q --tb=short -m "not slow" --ignore=tests/test_e2e.py
    ;;
  e2e)
    echo "=== (alias) slow ===" >&2
    exec "$0" slow
    ;;
  *)
    echo "usage: $0 {unit|smoke|slow|full}" >&2
    exit 1
    ;;
esac
