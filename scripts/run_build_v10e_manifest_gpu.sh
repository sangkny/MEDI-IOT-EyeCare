#!/bin/bash
# =============================================================
# 파일명: run_build_v10e_manifest_gpu.sh
# 목적: GPU Docker — gl_extra2 + unified_v10e manifest 생성
# 히스토리:
#   2026-06-13 - 최초 작성
# =============================================================
set -euo pipefail

REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
DATASET_ROOT="${DATASET_ROOT:-$HOME/workspace/dataset}"
IMAGE="${TRAIN_IMAGE:-medi-train:gpu}"
PATH_ROOT="${PATH_ROOT:-Glaucoma_extra2}"
EXTRA2_ENHANCED="${EXTRA2_ENHANCED:-0}"

EXTRA_ARGS=()
if [ "$EXTRA2_ENHANCED" = "1" ]; then
  PATH_ROOT="enhanced_cache"
  EXTRA_ARGS+=(--extra2-enhanced-paths)
fi

echo "=== build gl_extra2 + unified_v10e (path_root=$PATH_ROOT) ==="

docker run --rm \
  -v "$DATASET_ROOT:/dataset" \
  -v "$REPO:/workspace" \
  --entrypoint bash \
  "$IMAGE" -c "
    set -euo pipefail
    cd /workspace
    python3 scripts/build_gl_extra2_manifest.py --data-root /dataset --path-root $PATH_ROOT
    python3 scripts/build_v10e_manifest.py ${EXTRA_ARGS[*]}
  "

echo "OK manifests → training/manifests/gl_extra2.json unified_v10e.json"
