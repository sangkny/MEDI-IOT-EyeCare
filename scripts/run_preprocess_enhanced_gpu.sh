#!/bin/bash
# =============================================================
# 파일명: run_preprocess_enhanced_gpu.sh
# 목적: GPU — enhanced_cache 전처리 백그라운드 (medi-train:gpu)
# 히스토리:
#   2026-06-12 - 최초 작성
# =============================================================
set -euo pipefail

REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
DATASET_ROOT="${DATASET_ROOT:-$HOME/workspace/dataset}"
DR_DATA_DIR="${DR_DATA_DIR:-$REPO/data}"
IMAGE="${TRAIN_IMAGE:-medi-train:gpu}"
LOG="${LOG:-$REPO/preprocess_enhanced.log}"

echo "=== preprocess_enhanced (background) ==="
echo "log: $LOG"

nohup docker run --rm \
  --shm-size=4g \
  -v "$DATASET_ROOT:/dataset" \
  -v "$DR_DATA_DIR:/data_dr" \
  -v "$REPO:/workspace" \
  "$IMAGE" \
  bash -c 'python3 /workspace/scripts/preprocess_enhanced.py' \
  > "$LOG" 2>&1 &

echo "PID $! — tail -f $LOG"
