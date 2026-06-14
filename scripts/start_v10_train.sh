#!/bin/bash
# =============================================================
# 파일명: start_v10_train.sh
# 목적: v10/v10b/v10c/v10d 멀티태스크 훈련 — V10B/V10C/V10D env
# 히스토리:
#   2026-06-12 - V10E 블록 (extra2 데이터 + gl_w=0.28)
#   2026-06-12 - V10D 블록 (GL 증강+오버샘플+weight0.32)
#   2026-06-11 - 현재 상태 문서화 + 히스토리 추가
# =============================================================
# v10 통합 멀티태스크 훈련 — GPU 서버에서 실행
# 예: bash scripts/start_v10_train.sh
# v10b: V10B=1  v10c: V10C=1  v10d: V10D=1  v10e: V10E=1
set -euo pipefail

REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
DATASET_ROOT="${DATASET_ROOT:-$HOME/workspace/dataset}"
DR_DATA_DIR="${DR_DATA_DIR:-$REPO/data}"
IMAGE="${TRAIN_IMAGE:-medi-train:gpu}"
MANIFEST="${MANIFEST:-training/manifests/unified_v10.json}"
GL_OVERSAMPLE="${GL_OVERSAMPLE:-1.0}"

if [ "${V10E:-0}" = "1" ]; then
  OUTPUT="${OUTPUT:-models/retinal_v10e}"
  BATCH_SIZE=64
  WARMUP_EPOCHS=8
  DR_WEIGHT=0.25
  GL_WEIGHT=0.28
  AMD_WEIGHT=0.17
  MYO_WEIGHT=0.17
  MULTI_WEIGHT=0.13
  GL_OVERSAMPLE=1.0
  MANIFEST="${MANIFEST:-training/manifests/unified_v10e.json}"
  echo "=== v10e (extra2 2375 + base GL, gl_w=0.28, enhanced_cache paths) ==="
elif [ "${V10D:-0}" = "1" ]; then
  OUTPUT="${OUTPUT:-models/retinal_v10d}"
  BATCH_SIZE=64
  WARMUP_EPOCHS=8
  DR_WEIGHT=0.25
  GL_WEIGHT=0.32
  AMD_WEIGHT=0.17
  MYO_WEIGHT=0.17
  MULTI_WEIGHT=0.09
  GL_OVERSAMPLE=1.5
  echo "=== v10d (GL 증강 + weight 0.32 + oversample 1.5) ==="
elif [ "${V10C:-0}" = "1" ]; then
  OUTPUT="${OUTPUT:-models/retinal_v10c}"
  BATCH_SIZE=64
  WARMUP_EPOCHS=8
  DR_WEIGHT=0.25
  GL_WEIGHT=0.28
  AMD_WEIGHT=0.17
  MYO_WEIGHT=0.17
  MULTI_WEIGHT=0.13
  echo "=== v10c retrain (GL weight 0.28) ==="
elif [ "${V10B:-0}" = "1" ]; then
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
  OUTPUT="${OUTPUT:-models/retinal_v10}"
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
echo "weights:  dr=$DR_WEIGHT gl=$GL_WEIGHT amd=$AMD_WEIGHT myo=$MYO_WEIGHT multi=$MULTI_WEIGHT warmup=$WARMUP_EPOCHS gl_oversample=$GL_OVERSAMPLE"

if [ ! -f "$REPO/$MANIFEST" ]; then
  echo "FAIL: $MANIFEST not found"
  if [ "${V10E:-0}" = "1" ]; then
    echo "  → bash scripts/run_build_v10e_manifest_gpu.sh"
    echo "  → enhanced 후: EXTRA2_ENHANCED=1 bash scripts/run_build_v10e_manifest_gpu.sh"
  else
    echo "  → bash scripts/build_v10_manifest.sh"
  fi
  exit 1
fi

docker run --gpus all --rm \
  --shm-size=4g \
  --entrypoint bash \
  -e PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
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
      --gl-oversample $GL_OVERSAMPLE \
      --early-stop 12 \
      --device cuda \
      2>&1 | tee /tmp/retinal_v10_train.log | tee /workspace/$OUTPUT/train.log
  "

echo "OK log → /tmp/retinal_v10_train.log"
