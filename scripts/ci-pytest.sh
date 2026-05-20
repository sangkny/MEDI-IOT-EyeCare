#!/usr/bin/env bash
# GHA — unit 마커 테스트만 (DB/Redis/uvicorn/ONNX/LLM 없음)
set -euo pipefail
cd "$(dirname "$0")/.."
pip install -q pytest-timeout 2>/dev/null || true
python -m pytest tests/ -q \
  -m "unit and not requires_db and not requires_llm and not requires_onnx" \
  --timeout=60 \
  --tb=short
