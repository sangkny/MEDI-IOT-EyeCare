#!/bin/bash
# 목적: 전처리 결과 품질 검증
# IRB: 국내 임상기관 IRB 승인 (2019) — 로컬 전용
set -e
ssh smartvisionglobal@192.168.0.23 "
cd ~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare
docker run --rm --entrypoint bash \
  -v ~/workspace/dataset:/dataset \
  -v ~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare:/workspace \
  medi-train:gpu -c '
    pip install openpyxl --break-system-packages -q &&
    python3 /workspace/scripts/verify_korean_gl_output.py
  '
"
