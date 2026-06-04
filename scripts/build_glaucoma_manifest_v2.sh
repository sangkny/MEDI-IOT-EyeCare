#!/bin/bash
# Glaucoma v2 manifest — G1020+REFUGE+ORIGA+AIROGS+RIM-ONE (~10,809장)
# GPU 서버에서 실행
set -euo pipefail

DATA_ROOT="${DATA_ROOT:-$HOME/workspace/dataset/Glaucoma_raw}"
EXTRA_ROOT="${EXTRA_ROOT:-$HOME/workspace/dataset/Glaucoma_extra}"
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
OUTPUT="${OUTPUT:-training/manifests/glaucoma_v2.json}"
IMAGE="${TRAIN_IMAGE:-medi-train:gpu}"
DATASET_PARENT="$(dirname "$DATA_ROOT")"

echo "=== build_glaucoma_manifest_v2 ==="
echo "data-root:  $DATA_ROOT"
echo "extra-root: $EXTRA_ROOT"
echo "output:     $REPO/$OUTPUT"

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
      --sources g1020,refuge,origa,airogs,rimone \
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
print(\"data_dir:\", m.get(\"data_dir\"))
PY
  "

echo "OK → $REPO/$OUTPUT"
