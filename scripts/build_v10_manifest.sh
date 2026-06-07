#!/bin/bash
# v10 통합 manifest — 5 manifest merge → unified_v10.json
# GPU 서버에서 실행
set -euo pipefail

DATASET_ROOT="${DATASET_ROOT:-$HOME/workspace/dataset}"
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
OUTPUT="${OUTPUT:-training/manifests/unified_v10.json}"
IMAGE="${TRAIN_IMAGE:-medi-train:gpu}"
DR_MANIFEST="${DR_MANIFEST:-training/manifests/unified_v4.json}"

echo "=== build_v10_manifest ==="
echo "dataset: $DATASET_ROOT"
echo "output:  $REPO/$OUTPUT"

docker run --gpus all --rm \
  --shm-size=4g \
  --entrypoint bash \
  -v "$DATASET_ROOT:/dataset:ro" \
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
      --data-dir /dataset

    python3 <<'PY'
import json
m = json.load(open(\"$OUTPUT\"))
print(f\"total={m['total']} splits={m.get('splits')} coverage={m.get('label_coverage')}\")
print(f\"sources={m.get('sources')}\")
PY
  "

echo "OK → $REPO/$OUTPUT"
