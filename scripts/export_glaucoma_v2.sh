#!/bin/bash
# retinal_glaucoma_v2 ONNX export — GPU 또는 개발 PC
set -euo pipefail

ROOT="${ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
IMAGE="${TRAIN_IMAGE:-medi-train:gpu}"

echo "=== export_glaucoma_v2 ==="
echo "root: $ROOT"

docker run --rm --entrypoint bash \
  -v "$ROOT:/workspace" \
  "$IMAGE" -c "
    set -euo pipefail
    cd /workspace
    python3 scripts/export_glaucoma_v2.py \
      --checkpoint models/retinal_glaucoma_v2/best.pt \
      --output models/retinal_glaucoma_v2.onnx \
      --meta models/retinal_glaucoma_v2.meta.json
  "

echo "OK → $ROOT/models/retinal_glaucoma_v2.onnx"
