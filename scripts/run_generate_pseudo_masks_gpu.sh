#!/bin/bash
# SAM pseudo-mask 생성 (GPU Docker — 중첩 docker run 금지)
set -euo pipefail
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
DATASET_ROOT="${DATASET_ROOT:-$HOME/workspace/dataset}"
DR_DATA_DIR="${DR_DATA_DIR:-$REPO/data}"
CHECKPOINT_DIR="${CHECKPOINT_DIR:-$HOME/workspace/checkpoints}"
PHASE="${PHASE:-g1020}"
LIMIT="${LIMIT:-0}"

docker run --rm --entrypoint bash --gpus all \
  -v "$DATASET_ROOT:/dataset" \
  -v "$DR_DATA_DIR:/data_dr:ro" \
  -v "$CHECKPOINT_DIR:/checkpoints:ro" \
  -v "$REPO:/workspace" \
  medi-train:gpu -c "
    set -euo pipefail
    pip install segment-anything timm --break-system-packages -q
    LIMIT_ARG=
    if [ \"${LIMIT}\" != \"0\" ]; then LIMIT_ARG=\"--limit ${LIMIT}\"; fi
    python3 /workspace/scripts/generate_pseudo_masks_sam.py \
      --phase ${PHASE} \
      --checkpoint /checkpoints/sam_vit_b_01ec64.pth \
      \$LIMIT_ARG
  "
