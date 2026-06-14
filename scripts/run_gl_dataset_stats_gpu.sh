#!/bin/bash
# =============================================================
# 파일명: run_gl_dataset_stats_gpu.sh
# 목적: GPU — GL 데이터셋 장수 집계 (medi-train:gpu)
# 히스토리:
#   2026-06-12 - 최초 작성
# =============================================================
set -euo pipefail

DATASET_ROOT="${DATASET_ROOT:-$HOME/workspace/dataset}"
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
IMAGE="${TRAIN_IMAGE:-medi-train:gpu}"

docker run --rm \
  -v "$DATASET_ROOT:/dataset" \
  -v "$REPO:/workspace:ro" \
  --entrypoint bash \
  "$IMAGE" -c '
    echo "=== Glaucoma_raw ==="
    find /dataset/Glaucoma_raw \( -iname "*.jpg" -o -iname "*.png" \) 2>/dev/null | wc -l
    echo "=== Glaucoma_extra ==="
    find /dataset/Glaucoma_extra \( -iname "*.jpg" -o -iname "*.png" \) 2>/dev/null | wc -l
    echo "=== Glaucoma_extra2 ==="
    find /dataset/Glaucoma_extra2 \( -iname "*.jpg" -o -iname "*.png" \) 2>/dev/null | wc -l
    if [ -f /workspace/training/manifests/unified_v10.json ]; then
      python3 <<PY
import json
m = json.load(open("/workspace/training/manifests/unified_v10.json"))
gl = [s for s in m["samples"] if "glaucoma" in s.get("available_labels", {})]
normal = [s for s in gl if s["available_labels"]["glaucoma"] == 0]
abnormal = [s for s in gl if s["available_labels"]["glaucoma"] == 1]
print(f"unified_v10 GL: {len(gl)} (normal={len(normal)} abnormal={len(abnormal)} ratio={len(abnormal)/max(len(gl),1)*100:.1f}%)")
PY
    fi
  '
