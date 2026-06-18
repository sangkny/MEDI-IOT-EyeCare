#!/bin/bash
# v12 smoke2 — backbone unfreeze(epoch10) 통과 검증
set -euo pipefail
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
docker run --rm --entrypoint bash --gpus all \
  -v ~/workspace/dataset:/dataset \
  -v "$REPO/data:/data_dr" \
  -v "$REPO:/workspace" \
  medi-train:gpu -c '
    cd /workspace &&
    python3 training/train_v10.py \
      --manifest training/manifests/unified_v12.json \
      --output models/retinal_v12_smoke2 \
      --smoke --seg-head --epochs 11 --warmup-epochs 9
  '
