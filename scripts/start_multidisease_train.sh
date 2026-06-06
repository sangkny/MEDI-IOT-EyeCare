#!/bin/bash
# 다질환 멀티레이블 훈련 — GPU 서버에서 실행
# 예: bash scripts/start_multidisease_train.sh
set -euo pipefail

REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
DATASET_ROOT="${DATASET_ROOT:-$HOME/workspace/dataset}"
IMAGE="${TRAIN_IMAGE:-medi-train:gpu}"
MANIFEST="${MANIFEST:-training/manifests/multidisease_v1.json}"
OUTPUT="${OUTPUT:-models/retinal_multidisease_v1}"

echo "=== start_multidisease_train ==="
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
    python3 training/train_multidisease.py \
      --manifest $MANIFEST \
      --pretrained models/retinal_v4.pt \
      --output $OUTPUT \
      --epochs 60 \
      --batch-size 32 \
      --lr 1e-4 \
      --early-stop 12 \
      --device cuda \
      2>&1 | tee /tmp/retinal_multidisease_train.log
  "

echo "OK log → /tmp/retinal_multidisease_train.log"
