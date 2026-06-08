#!/bin/bash
# GPU 서버 v10b 훈련 환경 검증 — svg-server (192.168.0.23)
set -euo pipefail

REPO="${REPO:-$HOME/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare}"
DATASET="${DATASET_ROOT:-$HOME/workspace/dataset}"

echo "=== DR resized_cache ==="
ls "$REPO/data/resized_cache/" | head -3
DR_COUNT=$(find "$REPO/data/resized_cache" -name '*.jpg' | wc -l)
echo "DR jpg count: $DR_COUNT"

echo "=== GL/AMD/MYO/Multi resized_cache ==="
ls "$DATASET/resized_cache/"
GL_COUNT=$(find "$DATASET/resized_cache" -name '*.jpg' | wc -l)
echo "dataset jpg count: $GL_COUNT"

echo "=== unified_v10.json path check ==="
python3 <<'PY'
import json
from pathlib import Path

repo = Path.home() / "workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare"
manifest = repo / "training/manifests/unified_v10.json"
data = json.loads(manifest.read_text(encoding="utf-8"))
checked = {}
for s in data["samples"]:
    labels = list(s.get("available_labels", {}).keys())
    if not labels:
        continue
    label = labels[0]
    if label in checked:
        continue
    p = s["path"]
    if p.startswith("/data_dr"):
        full = Path(str(p).replace("/data_dr", str(repo / "data"), 1))
    elif p.startswith("/"):
        full = Path(p)
    else:
        full = Path("/home/smartvisionglobal/workspace/dataset") / p
    checked[label] = (str(full)[:72], full.exists())

ok = all(v[1] for v in checked.values())
for k, (path, exists) in sorted(checked.items()):
    print(f"{k:15s} exists={exists} {path}")
print("ALL_EXISTS=" + str(ok))
PY

echo "=== V10B block ==="
grep -A 18 'V10B' "$REPO/scripts/start_v10_train.sh" | head -20
