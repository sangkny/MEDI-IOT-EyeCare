#!/bin/bash
# =============================================================
# 파일명: build_multidisease_manifest.sh
# 목적: build_multidisease_manifest.sh 실행 스크립트
# 히스토리:
#   2026-06-11 - 현재 상태 문서화 + 히스토리 추가
# =============================================================
# 다질환 manifest 생성 — GPU 서버에서 실행
# 예: bash scripts/build_multidisease_manifest.sh
set -euo pipefail

DATASET_ROOT="${DATASET_ROOT:-$HOME/workspace/dataset}"
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
OUTPUT="${OUTPUT:-training/manifests/multidisease_v1.json}"
IMAGE="${TRAIN_IMAGE:-medi-train:gpu}"

echo "=== build_multidisease_manifest ==="
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
      --task multidisease \
      --data-root /dataset/Multidisease_raw \
      --extra-root /dataset/Multidisease_raw \
      --sources rfmid,odir \
      --output $OUTPUT
    python3 <<'PY'
import json
m = json.load(open(\"$OUTPUT\"))
total = m[\"total\"]
classes = m.get(\"label_classes\", [])
stats = m.get(\"class_stats\", {})
pos_any = sum(1 for s in m[\"samples\"] if any(int(v) for v in (s.get(\"labels\") or {}).values()))
print(f\"총 {total}장 | any-label: {pos_any} ({pos_any/total*100:.1f}%)\")
print(f\"sources: {m.get('sources')}\")
print(f\"classes: {len(classes)} | train/val/test: \", end=\"\")
print(
    sum(1 for s in m['samples'] if s['split']=='train'), \"/\",
    sum(1 for s in m['samples'] if s['split']=='val'), \"/\",
    sum(1 for s in m['samples'] if s['split']=='test'),
)
top = sorted(stats.items(), key=lambda kv: kv[1], reverse=True)[:8]
print(\"top8:\", \", \".join(f\"{k}={v}\" for k, v in top))
PY
  "

echo "OK → $REPO/$OUTPUT"
