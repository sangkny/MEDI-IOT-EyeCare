#!/bin/bash
# 목적: 수정본(glaucoma_modified) 전처리
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
    python3 /workspace/scripts/preprocess_korean_glaucoma.py ${DRY}
  '
"
