#!/bin/bash
# 목적: 수정본(glaucoma_modified) 전처리 — 레이아웃 분석 선행 권장
# IRB: 국내 임상기관 IRB 승인 (2019) — 로컬 전용
# 사용법:
#   ssh gpu-smart "cd ~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare && bash scripts/run_preprocess_korean_gl_gpu.sh"
set -euo pipefail
DRY=${1:-}
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
IMAGE="${TRAIN_IMAGE:-medi-train:gpu}"
DATASET="${DATASET_ROOT:-$HOME/workspace/dataset}"

cd "$REPO"
docker run --rm --entrypoint bash \
  -v "$DATASET:/dataset" \
  -v "$REPO:/workspace" \
  "$IMAGE" -c "
    pip install openpyxl --break-system-packages -q 2>/dev/null || true
    if [ ! -f /workspace/crop_layout_analysis.json ]; then
      echo 'WARN: crop_layout_analysis.json missing — run run_analyze_crop_layout_gpu.sh first'
    fi
    python3 /workspace/scripts/preprocess_korean_glaucoma.py ${DRY}
  "
