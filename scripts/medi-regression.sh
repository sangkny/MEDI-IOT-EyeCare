#!/usr/bin/env bash
# =============================================================
# 파일명: medi-regression.sh
# 목적: MEDI-IOT 전체 회귀 테스트 — quick/unit/smoke/slow/full-mock
# 히스토리:
#   2026-06-16 - quick · full-mock · slow-26b 추가, compose 기본 e4b, 26b opt-in
#   2026-06-12 - LLM mock + .env.test (e4b only), slow 모드 분리
#   2026-06-11 - unit/smoke/e2e/full 모드 정리 + pytest 마커 연동
# =============================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODE="${1:-unit}"
COMPOSE="${COMPOSE_FILE:-../docker-compose.dev.yml}"
SERVICE="${MEDI_SERVICE:-medi-iot-api}"
ENV_FILE="${ENV_FILE:-.env.test}"

_exec_env() {
  local mode="${1:-mock}"
  shift
  local -a extra=()
  # .env.test 는 tests/conftest.py 가 setdefault 로 로드 — exec --env-file 미지원
  case "$mode" in
    mock)
      extra+=(-e AGENT_FOUR_AGENT_MOCK=1 -e PYTEST_LLM_MOCK=1)
      ;;
    live-e4b|live)
      extra+=(-e MEDI_USE_26B=0)
      extra+=(-e LOCAL_HEAVY_MODEL=google/gemma-4-e4b)
      extra+=(-e LOCAL_VISION_MODEL=google/gemma-4-e4b)
      extra+=(-e LOCAL_FAST_MODEL=google/gemma-4-e4b)
      ;;
    live-26b)
      extra+=(-e MEDI_USE_26B=1)
      extra+=(-e LOCAL_HEAVY_MODEL=google/gemma-4-26b-a4b)
      extra+=(-e LOCAL_VISION_MODEL=google/gemma-4-26b-a4b)
      extra+=(-e MEDI_VISION_MODELS=google/gemma-4-26b-a4b,mistralai/mistral-7b-instruct-v0.3)
      ;;
    *)
      echo "internal error: unknown exec mode '$mode'" >&2
      exit 2
      ;;
  esac
  docker compose -f "$COMPOSE" exec -T "${extra[@]}" "$SERVICE" python -m pytest "$@"
}

case "$MODE" in
  quick)
    echo "=== MEDI regression: quick (~15min, not slow · not requires_llm · LLM mock) ==="
    _exec_env mock tests/ -q --tb=short \
      -m "not slow and not requires_llm" --ignore=tests/test_e2e.py
    ;;
  unit)
    echo "=== MEDI regression: unit (~2min, LLM mock, LM Studio 불필요) ==="
    _exec_env mock tests/ -q --tb=short -m "unit" --ignore=tests/test_e2e.py
    ;;
  smoke)
    echo "=== MEDI regression: smoke (~5min, API + LLM mock) ==="
    _exec_env mock tests/ -q --tb=short \
      -m "unit or (integration and not slow and not requires_llm)" --ignore=tests/test_e2e.py
    ;;
  slow)
    echo "=== MEDI regression: slow (~30min, LM Studio e4b only · MEDI_USE_26B=0) ==="
    _exec_env live-e4b tests/ -q --tb=short -m "slow or requires_llm"
    ;;
  slow-26b)
    echo "=== MEDI regression: slow-26b (~60min+, LM Studio 26b · MEDI_USE_26B=1) ==="
    _exec_env live-26b tests/ -q --tb=short -m "slow or requires_llm"
    ;;
  full-mock)
    echo "=== MEDI regression: full-mock (~60min, not slow · LLM mock · LM Studio 불필요) ==="
    _exec_env mock tests/ -q --tb=short -m "not slow" --ignore=tests/test_e2e.py
    ;;
  full)
    echo "WARN: 'full' → 'full-mock' (LLM mock). 실 LLM은 'slow' 또는 'slow-26b' 사용." >&2
    exec "$0" full-mock
    ;;
  e2e)
    echo "=== (alias) slow (e4b) ===" >&2
    exec "$0" slow
    ;;
  *)
    echo "usage: $0 {quick|unit|smoke|slow|slow-26b|full-mock|full}" >&2
    exit 1
    ;;
esac
