#!/usr/bin/env bash
# =============================================================
# 파일명: medi-regression.sh
# 목적: MEDI-IOT 전체 회귀 테스트 — unit/smoke/e2e/full 모드
# 히스토리:
#   2026-06-11 - 현재 상태 문서화 + 히스토리 추가
#   2026-06-11 - unit/smoke/e2e/full 모드 정리 + pytest 마커 연동
#   2026-06-11 - v4 단일모델 → v10c 5질환 멀티모델 확장
# =============================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODE="${1:-unit}"
COMPOSE="${COMPOSE_FILE:-../docker-compose.dev.yml}"
SERVICE="${MEDI_SERVICE:-medi-iot-api-dev}"

_run() {
  docker compose -f "$COMPOSE" exec -T "$SERVICE" python -m pytest "$@"
}

case "$MODE" in
  unit)
    echo "=== MEDI regression: unit (~2min, mock, LLM 불필요) ==="
    _run tests/ -q --tb=short -m "unit" --ignore=tests/test_e2e.py
    ;;
  smoke)
    echo "=== MEDI regression: smoke (~5min, API 연결) ==="
    _run tests/ -q --tb=short -m "integration and not slow and not requires_llm"
    ;;
  e2e)
    echo "=== MEDI regression: e2e (~30min, LM Studio 필요) ==="
    _run tests/ -q --tb=short -m "slow or requires_llm"
    ;;
  full)
    echo "=== MEDI regression: full (~60min) ==="
    _run tests/ -q --tb=short -m "not slow" --ignore=tests/test_e2e.py
    ;;
  *)
    echo "usage: $0 {unit|smoke|e2e|full}" >&2
    exit 1
    ;;
esac
