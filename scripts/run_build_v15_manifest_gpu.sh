#!/bin/bash
# unified_v14 → unified_v15 manifest (GPU 서버 / Docker)
set -euo pipefail
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
IMAGE="${TRAIN_IMAGE:-medi-train:gpu}"
DATASET_ROOT="${DATASET_ROOT:-$HOME/workspace/dataset}"

docker run --rm --entrypoint bash \
  -v "$DATASET_ROOT:/dataset:ro" \
  -v "$REPO:/workspace" \
  "$IMAGE" -c "
    set -euo pipefail
    cd /workspace
    if [ ! -f training/manifests/unified_v14.json ]; then
      python3 scripts/build_v14_manifest.py
    fi
    python3 scripts/build_v15_manifest.py
  "

echo "OK → $REPO/training/manifests/unified_v15.json"
