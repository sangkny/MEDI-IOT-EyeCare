#!/bin/bash
# GPU medi-train:gpu 컨테이너에 SAM + timm 설치 (1회성 검증)
set -euo pipefail
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
docker run --rm --entrypoint bash \
  -v "$REPO:/workspace" \
  medi-train:gpu -c '
    pip install segment-anything timm --break-system-packages -q &&
    python3 -c "from segment_anything import sam_model_registry; print(\"SAM OK\")"
  '
