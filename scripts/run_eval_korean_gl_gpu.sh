#!/bin/bash
# 목적: v10c 한국인 녹내장 성능 평가
# IRB: 국내 임상기관 IRB 승인 (2019) — 로컬 전용
set -e
ssh smartvisionglobal@192.168.0.23 "
cd ~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare
docker run --rm --gpus all --entrypoint bash \
  -v ~/workspace/dataset:/dataset \
  -v ~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare:/workspace \
  medi-train:gpu -c '
    pip install onnxruntime-gpu scikit-learn --break-system-packages -q &&
    python3 /workspace/scripts/eval_korean_gl.py
  '
"
