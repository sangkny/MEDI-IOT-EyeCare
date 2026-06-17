#!/bin/bash
# unified_v12 manifest 생성 (GPU)
set -euo pipefail
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
docker run --rm --entrypoint bash \
  -v ~/workspace/dataset:/dataset \
  -v "$REPO:/workspace" \
  medi-train:gpu -c 'python3 /workspace/scripts/build_v12_manifest.py'
