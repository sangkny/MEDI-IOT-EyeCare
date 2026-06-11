#!/bin/bash
# =============================================================
# 파일명: start_amd_train.sh
# 목적: start_amd_train.sh 실행 스크립트
# 히스토리:
#   2026-06-11 - 현재 상태 문서화 + 히스토리 추가
# =============================================================
# AMD 단독 훈련 — GPU 서버에서 실행
# 예: bash scripts/start_amd_train.sh
set -euo pipefail

REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
DATASET_ROOT="${DATASET_ROOT:-$HOME/workspace/dataset}"
IMAGE="${TRAIN_IMAGE:-medi-train:gpu}"
MANIFEST="${MANIFEST:-training/manifests/amd_v1.json}"
OUTPUT="${OUTPUT:-models/retinal_amd_v1}"

echo "=== start_amd_train ==="
echo "manifest: $MANIFEST"
echo "output:   $OUTPUT"

docker run --gpus all --rm \
  --shm-size=4g \
  --entrypoint bash \
  -v "$DATASET_ROOT:/dataset" \
  -v "$REPO:/workspace" \
  "$IMAGE" -c "
    set -euo pipefail
    cd /workspace
    mkdir -p $OUTPUT
    python3 training/train_amd.py \
      --manifest $MANIFEST \
      --pretrained models/retinal_v4.pt \
      --output $OUTPUT \
      --epochs 80 \
      --batch-size 32 \
      --lr 1e-4 \
      --focal-gamma 2.0 \
      --focal-alpha 0.75 \
      --early-stop 15 \
      --device cuda \
      2>&1 | tee /tmp/retinal_amd_train.log
  "

echo "OK log → /tmp/retinal_amd_train.log"
