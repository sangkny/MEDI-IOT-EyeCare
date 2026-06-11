#!/usr/bin/env bash
# =============================================================
# 파일명: gpu_export_v10_onnx.sh
# 목적: gpu_export_v10_onnx.sh 실행 스크립트
# 히스토리:
#   2026-06-11 - 현재 상태 문서화 + 히스토리 추가
# =============================================================
set -euo pipefail
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
docker run --rm --entrypoint bash \
  -v "$REPO:/workspace" \
  medi-train:gpu -c "cd /workspace && python3 scripts/export_v10_onnx.py"
