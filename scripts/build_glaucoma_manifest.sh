#!/bin/bash
# Glaucoma manifest 생성 — GPU 서버에서 실행
# 예: DATA_ROOT=~/workspace/dataset/Glaucoma_raw bash scripts/build_glaucoma_manifest.sh
set -euo pipefail

DATA_ROOT="${DATA_ROOT:-$HOME/workspace/dataset/Glaucoma_raw}"
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
OUTPUT="${OUTPUT:-training/manifests/glaucoma_v1.json}"
IMAGE="${TRAIN_IMAGE:-medi-train:gpu}"
DATASET_PARENT="$(dirname "$DATA_ROOT")"
DATASET_NAME="$(basename "$DATA_ROOT")"

echo "=== build_glaucoma_manifest ==="
echo "data-root: $DATA_ROOT"
echo "output:    $REPO/$OUTPUT"

docker run --rm --entrypoint bash \
  -v "$DATASET_PARENT:/dataset:ro" \
  -v "$REPO:/workspace" \
  "$IMAGE" -c "
    set -euo pipefail
    cd /workspace
    python3 training/make_manifest.py \
      --task glaucoma \
      --data-root /dataset/$DATASET_NAME \
      --sources g1020 refuge origa \
      --val-ratio 0.10 \
      --test-ratio 0.10 \
      --output $OUTPUT
    python3 <<'PY'
import json
m = json.load(open(\"$OUTPUT\"))
total = m[\"total\"]
samples = m[\"samples\"]
glaucoma = sum(1 for s in samples if s[\"label\"] == 1)
normal = sum(1 for s in samples if s[\"label\"] == 0)
print(f\"총 {total}장 | glaucoma: {glaucoma} ({glaucoma/total*100:.1f}%) | normal: {normal} ({normal/total*100:.1f}%)\")
print(f\"train: {sum(1 for s in samples if s['split']=='train')}\")
print(f\"val:   {sum(1 for s in samples if s['split']=='val')}\")
print(f\"test:  {sum(1 for s in samples if s['split']=='test')}\")
print(\"sources:\", m.get(\"sources\"))
PY
  "

echo "OK → $REPO/$OUTPUT"
