#!/bin/bash
# =============================================================
# 파일명: build_glaucoma_extra2_manifest.sh
# 목적: Glaucoma_extra2 (REFUGE/G1020/ORIGA/DRISHTI) manifest 생성
# 히스토리:
#   2026-06-12 - 최초 작성 (v10e 데이터 파이프라인)
# =============================================================
# 선행: bash scripts/download_gl_extra_datasets.sh
#       python scripts/preprocess_all.py
set -euo pipefail

EXTRA2_ROOT="${EXTRA2_ROOT:-$HOME/workspace/dataset/Glaucoma_extra2}"
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
OUTPUT="${OUTPUT:-training/manifests/glaucoma_extra2.json}"
IMAGE="${TRAIN_IMAGE:-medi-train:gpu}"
DATASET_PARENT="$(dirname "$EXTRA2_ROOT")"

echo "=== build_glaucoma_extra2_manifest ==="
echo "extra2-root: $EXTRA2_ROOT"
echo "output:      $REPO/$OUTPUT"

docker run --gpus all --rm \
  --shm-size=4g \
  --entrypoint bash \
  -v "$DATASET_PARENT:/dataset:ro" \
  -v "$REPO:/workspace" \
  "$IMAGE" -c "
    set -euo pipefail
    cd /workspace
    if [ ! -d /dataset/Glaucoma_extra2 ]; then
      echo 'FAIL: /dataset/Glaucoma_extra2 없음 — download_gl_extra_datasets.sh 먼저 실행'
      exit 1
    fi
    python3 training/make_manifest.py \
      --task glaucoma \
      --data-root /dataset/Glaucoma_extra2 \
      --sources refuge,g1020,origa,drishti \
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
print(f\"extra2 total={total} glaucoma={gl} normal={total-gl}\")
print(\"by source:\", dict(Counter(s.get(\"source\") for s in samples)))
PY
  "

echo "OK → $REPO/$OUTPUT"
