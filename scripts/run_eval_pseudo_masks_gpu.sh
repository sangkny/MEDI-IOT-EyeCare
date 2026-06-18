#!/bin/bash
# SAM pseudo-mask 품질 평가 (G1020 GT vs pseudo)
set -euo pipefail
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
DATASET_ROOT="${DATASET_ROOT:-$HOME/workspace/dataset}"
LIMIT="${LIMIT:-0}"
EXTRA=""
[ "$LIMIT" != "0" ] && EXTRA="--limit $LIMIT"

docker run --rm --entrypoint bash \
  -v "$DATASET_ROOT:/dataset" \
  -v "$REPO:/workspace" \
  medi-train:gpu -c "
    python3 /workspace/scripts/evaluate_pseudo_mask_quality.py $EXTRA
  "
