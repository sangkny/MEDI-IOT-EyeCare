#!/bin/bash
# =============================================================
# 파일명: build_glaucoma_manifest_v2.sh
# 목적: build_glaucoma_manifest_v2.sh 실행 스크립트
# 히스토리:
#   2026-06-11 - 현재 상태 문서화 + 히스토리 추가
# =============================================================
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
      --val-ratio 0.15 \
      --test-ratio 0.15 \
      --output $OUTPUT
    python3 <<'PY'
import json
from collections import Counter
m = json.load(open(\"$OUTPUT\"))
total = m[\"total\"]
samples = m[\"samples\"]
glaucoma = sum(1 for s in samples if s[\"label\"] == 1)
normal = sum(1 for s in samples if s[\"label\"] == 0)
val_samples = [s for s in samples if s[\"split\"] == \"val\"]
val_airogs = sum(1 for s in val_samples if s.get(\"source\") == \"airogs\")
print(f\"총 {total}장 | glaucoma: {glaucoma} ({glaucoma/total*100:.1f}%) | normal: {normal} ({normal/total*100:.1f}%)\")
print(f\"train: {sum(1 for s in samples if s['split']=='train')}\")
print(f\"val:   {len(val_samples)} (airogs in val: {val_airogs})\")
print(f\"test:  {sum(1 for s in samples if s['split']=='test')}\")
print(\"val by source:\", dict(Counter(s.get(\"source\") for s in val_samples)))
print(\"sources:\", m.get(\"sources\"))
print(\"data_dir:\", m.get(\"data_dir\"))
if val_airogs == 0:
    raise SystemExit(\"FAIL: val set has no AIROGS samples\")
PY
  "

echo "OK → $REPO/$OUTPUT"
