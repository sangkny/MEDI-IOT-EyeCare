#!/bin/bash
set -euo pipefail
docker run --rm --entrypoint bash \
  -v "${DATASET_ROOT:-$HOME/workspace/dataset}:/dataset" \
  -v "${REPO:-$HOME/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare}:/workspace" \
  medi-train:gpu -c "
    set -euo pipefail
    cd /workspace
    python3 scripts/build_v13_manifest.py --dataset-root /dataset --plan-b
  "
