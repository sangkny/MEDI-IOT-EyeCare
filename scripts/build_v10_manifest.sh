#!/bin/bash
# =============================================================
# 파일명: build_v10_manifest.sh
# 목적: build_v10_manifest.sh 실행 스크립트
# 히스토리:
#   2026-06-11 - 현재 상태 문서화 + 히스토리 추가
# =============================================================
# v10 통합 manifest — 5 manifest merge → unified_v10.json
# GPU 서버에서 실행
set -euo pipefail

DATASET_ROOT="${DATASET_ROOT:-$HOME/workspace/dataset}"
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
DR_DATA_DIR="${DR_DATA_DIR:-$REPO/data}"
OUTPUT="${OUTPUT:-training/manifests/unified_v10.json}"
IMAGE="${TRAIN_IMAGE:-medi-train:gpu}"
DR_MANIFEST="${DR_MANIFEST:-training/manifests/unified_v4.json}"

echo "=== build_v10_manifest ==="
echo "dataset: $DATASET_ROOT → /dataset"
echo "dr_data: $DR_DATA_DIR → /data_dr"
echo "output:  $REPO/$OUTPUT"

docker run --gpus all --rm \
  --shm-size=4g \
  --entrypoint bash \
  -v "$DATASET_ROOT:/dataset:ro" \
  -v "$DR_DATA_DIR:/data_dr:ro" \
  -v "$REPO:/workspace" \
  "$IMAGE" -c "
    set -euo pipefail
    cd /workspace

    if [ ! -f \"$DR_MANIFEST\" ]; then
      echo \"WARN: $DR_MANIFEST missing — build DR manifest first (APTOS/Messidor/IDRiD)\"
      echo \"  python3 training/make_manifest.py --data-root /dataset --sources aptos,messidor,idr --output $DR_MANIFEST\"
      exit 1
    fi

    for f in training/manifests/glaucoma_v2.json training/manifests/amd_v1.json \
             training/manifests/myopia_v1.json training/manifests/multidisease_v1.json; do
      if [ ! -f \"\$f\" ]; then
        echo \"FAIL: missing \$f — run respective build_*_manifest.sh first\"
        exit 1
      fi
    done

    python3 training/build_v10_manifest.py \
      --dr $DR_MANIFEST \
      --glaucoma training/manifests/glaucoma_v2.json \
      --amd training/manifests/amd_v1.json \
      --myopia training/manifests/myopia_v1.json \
      --multidisease training/manifests/multidisease_v1.json \
      --output $OUTPUT \
      --data-dir /dataset \
      --dr-data-dir /data_dr

    python3 <<'PY'
import json
m = json.load(open("$OUTPUT"))
print(f"total={m['total']} splits={m.get('splits')} coverage={m.get('label_coverage')}")
print(f"sources={m.get('sources')}")
print(f"data_dir={m.get('data_dir')} dr_data_dir={m.get('dr_data_dir')}")
dr_samples = [
    s for s in m["samples"]
    if "dr" in s.get("available_labels", {})
    and len(s.get("available_labels", {})) == 1
]
print(f"DR-only samples={len(dr_samples)}")
if dr_samples:
    print(f"first DR path={dr_samples[0]['path']}")
resized = sum(1 for s in dr_samples if "resized_cache" in s["path"])
print(f"resized_cache DR paths={resized}/{len(dr_samples)}")
if dr_samples and resized < len(dr_samples):
    raise SystemExit("FAIL: DR paths must use /data_dr/resized_cache/ — rebuild DR manifest or fix unified_v4 paths")
PY
  "

echo "OK → $REPO/$OUTPUT"
