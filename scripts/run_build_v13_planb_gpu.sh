#!/bin/bash
# v13 Plan B — ORIGA masks + unified_v13.json (GT only)
set -euo pipefail
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
DATASET_ROOT="${DATASET_ROOT:-$HOME/workspace/dataset}"

docker run --rm --entrypoint bash \
  -v "$DATASET_ROOT:/dataset" \
  -v "$REPO:/workspace" \
  medi-train:gpu -c "
    set -euo pipefail
    cd /workspace
    echo '=== ORIGA masks ==='
    python3 scripts/build_disc_cup_masks.py --origa --dataset-root /dataset
    echo '=== v13 manifest (Plan B) ==='
    python3 scripts/build_v13_manifest.py --dataset-root /dataset --plan-b
  "
