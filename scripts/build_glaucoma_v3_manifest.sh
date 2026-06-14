#!/bin/bash
# =============================================================
# 파일명: build_glaucoma_v3_manifest.sh
# 목적: glaucoma_v2 + Glaucoma_extra2 병합 manifest (v10e용)
# 히스토리:
#   2026-06-12 - 최초 작성
# =============================================================
set -euo pipefail

REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
DATA_ROOT="${DATA_ROOT:-$HOME/workspace/dataset/Glaucoma_raw}"
EXTRA_ROOT="${EXTRA_ROOT:-$HOME/workspace/dataset/Glaucoma_extra}"
EXTRA2_ROOT="${EXTRA2_ROOT:-$HOME/workspace/dataset/Glaucoma_extra2}"
OUTPUT="${OUTPUT:-training/manifests/glaucoma_v3.json}"
IMAGE="${TRAIN_IMAGE:-medi-train:gpu}"
DATASET_PARENT="$(dirname "$DATA_ROOT")"

echo "=== build_glaucoma_v3_manifest ==="
echo "data:   $DATA_ROOT"
echo "extra:  $EXTRA_ROOT"
echo "extra2: $EXTRA2_ROOT"
echo "output: $REPO/$OUTPUT"

docker run --gpus all --rm \
  --shm-size=4g \
  --entrypoint bash \
  -v "$DATASET_PARENT:/dataset:ro" \
  -v "$REPO:/workspace" \
  "$IMAGE" -c "
    set -euo pipefail
    cd /workspace
    python3 training/make_manifest.py \
      --task glaucoma \
      --data-root /dataset/Glaucoma_raw \
      --extra-root /dataset/Glaucoma_extra \
      --extra2-root /dataset/Glaucoma_extra2 \
      --sources g1020,refuge,origa,airogs,rimone,drishti \
      --val-ratio 0.15 \
      --test-ratio 0.15 \
      --output $OUTPUT
    python3 <<'PY'
import json
from collections import Counter
m = json.load(open(\"$OUTPUT\"))
samples = m[\"samples\"]
total = m[\"total\"]
gl = sum(1 for s in samples if s.get(\"label\") == 1)
print(f\"v3 total={total} glaucoma={gl} ({gl/total*100:.1f}%) normal={total-gl}\")
print(\"sources:\", m.get(\"sources\"))
PY
  "

echo "OK → $REPO/$OUTPUT"
