#!/usr/bin/env bash
set -euo pipefail
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
docker run --rm --entrypoint bash \
  -v "$REPO:/workspace" \
  medi-train:gpu -c "cd /workspace && python3 scripts/export_v10_onnx.py"
