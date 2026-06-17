#!/bin/bash
# G1020 disc/cup 마스크 생성 (GPU)
set -euo pipefail
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
docker run --rm --entrypoint bash \
  -v ~/workspace/dataset:/dataset \
  -v "$REPO:/workspace" \
  medi-train:gpu -c 'python3 /workspace/scripts/build_disc_cup_masks.py'
