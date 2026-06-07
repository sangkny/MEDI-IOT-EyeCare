#!/bin/bash
# v10 통합 멀티태스크 훈련 — GPU 서버에서 실행
# 예: bash scripts/start_v10_train.sh
set -euo pipefail

REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
DATASET_ROOT="${DATASET_ROOT:-$HOME/workspace/dataset}"
IMAGE="${TRAIN_IMAGE:-medi-train:gpu}"
MANIFEST="${MANIFEST:-training/manifests/unified_v10.json}"
OUTPUT="${OUTPUT:-models/retinal_v10}"

echo "=== start_v10_train ==="
echo "manifest: $MANIFEST"
echo "output:   $OUTPUT"

if [ ! -f "$REPO/$MANIFEST" ]; then
  echo "FAIL: $MANIFEST not found — run bash scripts/build_v10_manifest.sh first"
  exit 1
fi

docker run --gpus all --rm \
  --shm-size=4g \
  --entrypoint bash \
  -v "$DATASET_ROOT:/dataset:ro" \
  -v "$REPO:/workspace" \
  "$IMAGE" -c "
    set -euo pipefail
    cd /workspace
    mkdir -p $OUTPUT
    python3 training/train_v10.py \
      --manifest $MANIFEST \
      --pretrained models/retinal_v4.pt \
      --output $OUTPUT \
      --epochs 60 \
      --batch-size 32 \
      --lr 1e-4 \
      --finetune-lr 1e-5 \
      --warmup-epochs 10 \
      --early-stop 12 \
      --device cuda \
      2>&1 | tee /tmp/retinal_v10_train.log
  "

echo "OK log → /tmp/retinal_v10_train.log"
