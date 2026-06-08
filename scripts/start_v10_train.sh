#!/bin/bash
# v10 통합 멀티태스크 훈련 — GPU 서버에서 실행
# 예: bash scripts/start_v10_train.sh
# v10b (GL 개선): V10B=1 bash scripts/start_v10_train.sh
set -euo pipefail

REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
DATASET_ROOT="${DATASET_ROOT:-$HOME/workspace/dataset}"
DR_DATA_DIR="${DR_DATA_DIR:-$REPO/data}"
IMAGE="${TRAIN_IMAGE:-medi-train:gpu}"
MANIFEST="${MANIFEST:-training/manifests/unified_v10.json}"
OUTPUT="${OUTPUT:-models/retinal_v10}"

# v10b: GL AUC 개선 — loss weight 재조정 + warmup 단축
if [ "${V10B:-0}" = "1" ]; then
  OUTPUT="${OUTPUT:-models/retinal_v10b}"
  BATCH_SIZE=64
  WARMUP_EPOCHS=5
  DR_WEIGHT=0.25
  GL_WEIGHT=0.35
  AMD_WEIGHT=0.15
  MYO_WEIGHT=0.15
  MULTI_WEIGHT=0.10
  echo "=== v10b retrain (GL weight boost) ==="
else
  BATCH_SIZE=64
  WARMUP_EPOCHS=10
  DR_WEIGHT=0.30
  GL_WEIGHT=0.20
  AMD_WEIGHT=0.20
  MYO_WEIGHT=0.20
  MULTI_WEIGHT=0.10
fi

echo "=== start_v10_train ==="
echo "manifest: $MANIFEST"
echo "output:   $OUTPUT"
echo "dataset:  $DATASET_ROOT → /dataset"
echo "dr_data:  $DR_DATA_DIR → /data_dr"
echo "weights:  dr=$DR_WEIGHT gl=$GL_WEIGHT amd=$AMD_WEIGHT myo=$MYO_WEIGHT multi=$MULTI_WEIGHT warmup=$WARMUP_EPOCHS"

if [ ! -f "$REPO/$MANIFEST" ]; then
  echo "FAIL: $MANIFEST not found — run bash scripts/build_v10_manifest.sh first"
  exit 1
fi

docker run --gpus all --rm \
  --shm-size=4g \
  --entrypoint bash \
  -v "$DATASET_ROOT:/dataset:ro" \
  -v "$DR_DATA_DIR:/data_dr:ro" \
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
      --batch-size $BATCH_SIZE \
      --lr 1e-4 \
      --finetune-lr 1e-5 \
      --warmup-epochs $WARMUP_EPOCHS \
      --dr-weight $DR_WEIGHT \
      --gl-weight $GL_WEIGHT \
      --amd-weight $AMD_WEIGHT \
      --myo-weight $MYO_WEIGHT \
      --multi-weight $MULTI_WEIGHT \
      --early-stop 12 \
      --device cuda \
      2>&1 | tee /tmp/retinal_v10_train.log | tee /workspace/$OUTPUT/train.log
  "

echo "OK log → /tmp/retinal_v10_train.log"
