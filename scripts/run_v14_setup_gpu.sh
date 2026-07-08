#!/bin/bash
# STEP 5+8: v14 manifest build + stats + smoke test
set -euo pipefail
REPO=~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare
cd "$REPO"
git pull

echo "=== build v14 manifest ==="
docker run --rm --entrypoint bash \
  -v ~/workspace/dataset:/dataset \
  -v "$REPO":/workspace \
  medi-train:gpu -c '
    pip install openpyxl --break-system-packages -q
    python3 /workspace/scripts/build_v14_manifest.py
  '

echo "=== v14 stats ==="
docker run --rm --entrypoint bash \
  -v "$REPO":/workspace \
  medi-train:gpu -c '
python3 -c "
import json
m = json.load(open(\"/workspace/training/manifests/unified_v14.json\"))
s = m[\"samples\"]
total = len(s)
gl = sum(1 for x in s if (x.get(\"available_labels\") or {}).get(\"glaucoma\") == 1)
kr = sum(1 for x in s if x.get(\"korean_clinical\"))
ntg = sum(1 for x in s if (x.get(\"available_labels\") or {}).get(\"is_ntg\") == 1)
print(f\"total={total} GL={gl} korean={kr} NTG={ntg}\")
if gl:
    print(f\"korean ratio of GL: {kr/gl*100:.1f}%\")
"
'

echo "=== smoke test epochs=1 ==="
docker run --rm --entrypoint bash --gpus all \
  -v ~/workspace/dataset:/dataset \
  -v ~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare/data:/data_dr:ro \
  -v "$REPO":/workspace \
  medi-train:gpu -c '
    cd /workspace
    python3 training/train_v10.py \
      --manifest training/manifests/unified_v14.json \
      --pretrained models/retinal_v4.pt \
      --output models/retinal_v14_smoke \
      --smoke --epochs 1 --device cuda 2>&1 | tail -30
  '
