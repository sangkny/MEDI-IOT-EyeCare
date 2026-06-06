#!/bin/bash
# 근시 manifest 생성 — GPU 서버에서 실행
# 예: bash scripts/build_myopia_manifest.sh
set -euo pipefail

DATASET_ROOT="${DATASET_ROOT:-$HOME/workspace/dataset}"
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
OUTPUT="${OUTPUT:-training/manifests/myopia_v1.json}"
IMAGE="${TRAIN_IMAGE:-medi-train:gpu}"

echo "=== build_myopia_manifest ==="
echo "dataset:    $DATASET_ROOT"
echo "extra-root: $DATASET_ROOT/Multidisease_raw"
echo "output:     $REPO/$OUTPUT"

docker run --gpus all --rm \
  --shm-size=4g \
  --entrypoint bash \
  -v "$DATASET_ROOT:/dataset" \
  -v "$REPO:/workspace" \
  "$IMAGE" -c "
    set -euo pipefail
    cd /workspace
    python3 training/make_manifest.py \
      --task myopia \
      --data-root /dataset/Multidisease_raw \
      --extra-root /dataset/Multidisease_raw \
      --sources odir_myopia,rfmid_myopia \
      --output $OUTPUT
    python3 <<'PY'
import json
m = json.load(open(\"$OUTPUT\"))
total = m[\"total\"]
myopia = sum(1 for s in m[\"samples\"] if s[\"label\"] == 1)
normal = sum(1 for s in m[\"samples\"] if s[\"label\"] == 0)
print(f\"총 {total}장 | myopia: {myopia} ({myopia/total*100:.1f}%) | normal: {normal}\")
print(f\"train: {sum(1 for s in m['samples'] if s['split']=='train')}\")
print(f\"val:   {sum(1 for s in m['samples'] if s['split']=='val')}\")
print(f\"test:  {sum(1 for s in m['samples'] if s['split']=='test')}\")
print(\"sources:\", m.get(\"sources\"))
PY
  "

echo "OK → $REPO/$OUTPUT"
