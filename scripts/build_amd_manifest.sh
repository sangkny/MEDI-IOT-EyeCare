#!/bin/bash
# AMD manifest 생성 — GPU 서버에서 실행
# 예: bash scripts/build_amd_manifest.sh
set -euo pipefail

DATASET_ROOT="${DATASET_ROOT:-$HOME/workspace/dataset}"
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
OUTPUT="${OUTPUT:-training/manifests/amd_v1.json}"
IMAGE="${TRAIN_IMAGE:-medi-train:gpu}"

echo "=== build_amd_manifest ==="
echo "dataset:    $DATASET_ROOT"
echo "data-root:  $DATASET_ROOT/AMD_raw"
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
      --task amd \
      --data-root /dataset/AMD_raw \
      --extra-root /dataset/Multidisease_raw \
      --sources amdnet23,odir_amd,rfmid_amd \
      --output $OUTPUT
    python3 <<'PY'
import json
m = json.load(open(\"$OUTPUT\"))
total = m[\"total\"]
amd = sum(1 for s in m[\"samples\"] if s[\"label\"] == 1)
normal = sum(1 for s in m[\"samples\"] if s[\"label\"] == 0)
print(f\"총 {total}장 | AMD: {amd} ({amd/total*100:.1f}%) | normal: {normal}\")
print(f\"train: {sum(1 for s in m['samples'] if s['split']=='train')}\")
print(f\"val:   {sum(1 for s in m['samples'] if s['split']=='val')}\")
print(f\"test:  {sum(1 for s in m['samples'] if s['split']=='test')}\")
print(\"sources:\", m.get(\"sources\"))
PY
  "

echo "OK → $REPO/$OUTPUT"
