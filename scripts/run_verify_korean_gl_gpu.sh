#!/bin/bash
# 목적: 전처리 결과 품질 검증
# IRB: 국내 임상기관 IRB 승인 (2019) — 로컬 전용
# 사용법:
#   ssh gpu-smart "cd ~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare && bash scripts/run_verify_korean_gl_gpu.sh"
set -euo pipefail
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
IMAGE="${TRAIN_IMAGE:-medi-train:gpu}"
DATASET="${DATASET_ROOT:-$HOME/workspace/dataset}"

cd "$REPO"
docker run --rm --entrypoint bash \
  -v "$DATASET:/dataset" \
  -v "$REPO:/workspace" \
  "$IMAGE" -c "
    pip install openpyxl --break-system-packages -q 2>/dev/null || true
    python3 /workspace/scripts/verify_korean_gl_output.py
  "
