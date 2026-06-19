#!/bin/bash
set -euo pipefail
docker run --rm --entrypoint bash \
  -v "${DATASET_ROOT:-$HOME/workspace/dataset}:/dataset" \
  -v "${REPO:-$(cd "$(dirname "$0")/.." && pwd)}:/workspace" \
  medi-train:gpu -c "python3 /workspace/scripts/probe_origa_mask_values.py"
