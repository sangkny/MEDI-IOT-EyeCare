#!/bin/bash
# =============================================================
# 파일명: start_glaucoma_train.sh
# 목적: start_glaucoma_train.sh 실행 스크립트
# 히스토리:
#   2026-06-11 - 현재 상태 문서화 + 히스토리 추가
# =============================================================
# Glaucoma 단독 학습 — GPU 서버에서 실행 (--shm-size=4g 필수)
set -euo pipefail

ROOT="${ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT"
LOG="${LOG:-/tmp/retinal_glaucoma_train.log}"
DATA_ROOT="${DATA_ROOT:-$HOME/workspace/dataset}"
PRETRAINED="${PRETRAINED:-models/retinal_v4.pt}"

mkdir -p models/retinal_glaucoma_v1

echo "glaucoma train → $LOG"
echo "pretrained=$PRETRAINED"

nohup docker run --gpus all --rm \
  --shm-size=4g \
  --entrypoint bash \
  -v "$DATA_ROOT:/dataset:ro" \
  -v "$ROOT:/workspace" \
  medi-train:gpu -c "
    set -euo pipefail
    cd /workspace
    python3 training/train_glaucoma.py \
      --manifest training/manifests/glaucoma_v1.json \
      --pretrained $PRETRAINED \
      --output models/retinal_glaucoma_v1 \
      --epochs 80 \
      --batch-size 32 \
      --lr 1e-4 \
      --focal-gamma 2.0 \
      --focal-alpha 0.75 \
      --device cuda
  " > "$LOG" 2>&1 &

echo "PID: $!"
echo "tail -f $LOG"
