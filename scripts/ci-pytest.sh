#!/usr/bin/env bash
# =============================================================
# 파일명: ci-pytest.sh
# 목적: ci-pytest.sh 실행 스크립트
# 히스토리:
#   2026-06-11 - 현재 상태 문서화 + 히스토리 추가
# =============================================================
# GHA — unit 마커 테스트만 (DB/Redis/uvicorn/ONNX/LLM 없음)
set -euo pipefail
cd "$(dirname "$0")/.."
pip install -q pytest-timeout 2>/dev/null || true
python -m pytest tests/ -q \
  -m "unit and not requires_db and not requires_llm and not requires_onnx" \
  --timeout=60 \
  --tb=short
