#!/bin/bash
# Phase 1 예후 예측 파이프라인 — GPU Docker wrapper
set -euo pipefail

REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
IMAGE="${TRAIN_IMAGE:-medi-train:gpu}"
DATASET_ROOT="${DATASET_ROOT:-$HOME/workspace/dataset}"
BACKBONE="${BACKBONE:-models/retinal_v14/best.pt}"
SMOKE="${SMOKE:-0}"

SMOKE_FLAG=""
if [ "$SMOKE" = "1" ]; then
  SMOKE_FLAG="--smoke"
fi

echo "=== run_prognosis_gpu ==="
echo "dataset: $DATASET_ROOT"
echo "backbone: $BACKBONE"

docker run --rm --entrypoint bash --gpus all \
  -e PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  -v "$DATASET_ROOT:/dataset:ro" \
  -v "$REPO:/workspace" \
  "$IMAGE" -c "
    set -euo pipefail
    cd /workspace

    if [ ! -f /dataset/korean_glaucoma_fundus/timeseries_labels.csv ]; then
      echo 'building timeseries_labels.csv...'
      python3 scripts/build_timeseries_labels.py
    fi

    echo '--- STEP 0: timeseries analysis ---'
    python3 scripts/analyze_timeseries_labels.py

    echo '--- build prognosis pairs ---'
    python3 scripts/build_prognosis_pairs.py

    echo '--- train prognosis MLP (5-fold CV) ---'
    python3 scripts/train_prognosis_mlp.py \
      --backbone $BACKBONE \
      --output models/prognosis_v1 \
      $SMOKE_FLAG

    echo '--- eval prognosis ---'
    python3 scripts/eval_prognosis.py \
      --backbone $BACKBONE \
      --model models/prognosis_v1/best.pt \
      --output-json /dataset/korean_glaucoma_fundus/prognosis_results.json
  "

echo "OK results → $DATASET_ROOT/korean_glaucoma_fundus/prognosis_results.json"
