#!/bin/bash
# OSAM few-shot leave-one-out eval (GPU)
set -euo pipefail
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
DATASET_ROOT="${DATASET_ROOT:-$HOME/workspace/dataset}"
CHECKPOINT_DIR="${CHECKPOINT_DIR:-$HOME/workspace/checkpoints}"
LIMIT="${LIMIT:-10}"

docker run --rm --entrypoint bash --gpus all \
  -v "$DATASET_ROOT:/dataset" \
  -v "$CHECKPOINT_DIR:/checkpoints:ro" \
  -v "$REPO:/workspace" \
  medi-train:gpu -c "
    set -euo pipefail
    pip install segment-anything timm --break-system-packages -q
    python3 /workspace/scripts/generate_pseudo_masks_sam.py \
      --method osam --target eval --limit ${LIMIT} \
      --checkpoint /checkpoints/sam_vit_b_01ec64.pth
  "
