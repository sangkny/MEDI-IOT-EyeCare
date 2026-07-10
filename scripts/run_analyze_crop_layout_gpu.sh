#!/bin/bash
# 크롭 전 레이아웃 분석 — modified (기본) + origin (선택)
set -euo pipefail
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
IMAGE="${TRAIN_IMAGE:-medi-train:gpu}"
DATASET="${DATASET_ROOT:-$HOME/workspace/dataset}"
SOURCE="${SOURCE:-modified}"
OUT="${OUTPUT_JSON:-$REPO/crop_layout_analysis.json}"

if [ "$SOURCE" = "origin" ]; then
  INPUT="/dataset/korean_fundus_input/glaucoma_origin"
  OUT="${OUTPUT_JSON:-$REPO/crop_layout_analysis_origin.json}"
else
  INPUT="/dataset/korean_fundus_input/glaucoma_modified"
fi

echo "=== run_analyze_crop_layout_gpu source=$SOURCE ==="

docker run --rm --entrypoint bash \
  -v "$DATASET:/dataset:ro" \
  -v "$REPO:/workspace" \
  "$IMAGE" -c "
    set -euo pipefail
    pip install opencv-python-headless --break-system-packages -q 2>/dev/null || true
    python3 /workspace/scripts/analyze_crop_layout.py \
      --input-dir $INPUT \
      --source $SOURCE \
      --output-json /workspace/$(basename $OUT)
  "

echo "OK → $OUT"
