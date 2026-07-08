#!/bin/bash
# v15 smoke test — grade_head + device=cuda
set -euo pipefail
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
IMAGE="${TRAIN_IMAGE:-medi-train:gpu}"
DATASET_ROOT="${DATASET_ROOT:-$HOME/workspace/dataset}"
DR_DATA_DIR="${DR_DATA_DIR:-$REPO/data}"

if [ ! -f "$REPO/training/manifests/unified_v15.json" ]; then
  bash "$(dirname "$0")/run_build_v15_manifest_gpu.sh"
fi

docker run --rm --entrypoint bash --gpus all \
  -e PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  -v "$DATASET_ROOT:/dataset:ro" \
  -v "$DR_DATA_DIR:/data_dr:ro" \
  -v "$REPO:/workspace" \
  "$IMAGE" -c "
    set -euo pipefail
    cd /workspace
    python3 training/train_v10.py \
      --manifest training/manifests/unified_v15.json \
      --pretrained models/retinal_v14/best.pt \
      --output models/retinal_v15_smoke \
      --grade-head --grade-weight 0.05 \
      --smoke --epochs 1 --device cuda \
      --batch-size 32
  "

echo "OK v15 smoke → models/retinal_v15_smoke/"
