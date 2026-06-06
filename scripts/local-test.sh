#!/usr/bin/env bash
# conftest.py / HANDOVER 에서 참조하는 로컬 단위 테스트 진입점
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
bash "${SCRIPT_DIR}/medi-regression.sh" "${1:-unit}"
