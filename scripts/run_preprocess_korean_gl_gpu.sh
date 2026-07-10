#!/bin/bash
# 목적: 수정본(glaucoma_modified) 전처리 — 레이아웃 분석 선행 권장
# IRB: 국내 임상기관 IRB 승인 (2019) — 로컬 전용
set -e
DRY=${1:-}
ssh smartvisionglobal@192.168.0.23 "
cd ~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare
docker run --rm --entrypoint bash \
  -v ~/workspace/dataset:/dataset \
  -v ~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare:/workspace \
  medi-train:gpu -c '
    pip install openpyxl --break-system-packages -q &&
    if [ ! -f /workspace/crop_layout_analysis.json ]; then
      echo \"WARN: crop_layout_analysis.json missing — run run_analyze_crop_layout_gpu.sh first\"
    fi &&
    python3 /workspace/scripts/preprocess_korean_glaucoma.py ${DRY}
  '
"
