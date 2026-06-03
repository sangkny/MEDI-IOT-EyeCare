#!/bin/bash
set -euo pipefail
SSH_HOST="${SSH_HOST:-smartvisionglobal@192.168.0.23}"
GPU_REPO='~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare'
MEDI="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== GPU meta.json ==="
ssh -o ConnectTimeout=20 "$SSH_HOST" bash -s <<'REMOTE'
set -euo pipefail
cd ~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare
python3 <<'PY'
import json
from datetime import datetime, timezone
meta = {
    "arch": "retfound", "preprocess": "none", "image_size": 224,
    "onnx": "retinal_v8b_retfound.onnx", "pt": "retinal_v8b_retfound.pt",
    "version": "train-kit-v1", "trained_on": "unified_eyeq_good.json",
    "epochs": 100, "resume_from": "retinal_v8_retfound.pt", "resume_epoch": 34,
    "lr": 3e-6, "batch_size": 4, "best_val_qwk": 0.7105, "qwk": 0.7105,
    "data_count": 13582,
    "datasets": ["eyepacs_good", "aptos", "messidor2", "idrid"],
    "created_at": datetime.now(timezone.utc).isoformat(),
    "notes": "EyeQ Good 13,582 resume v8 ep34",
}
with open("models/retinal_v8b_retfound.meta.json", "w", encoding="utf-8") as f:
    json.dump(meta, f, indent=2)
print("OK QWK", meta["best_val_qwk"])
PY
REMOTE

echo "=== SCP meta.json ==="
mkdir -p "$MEDI/models"
scp -o ConnectTimeout=20 \
  "${SSH_HOST}:${GPU_REPO}/models/retinal_v8b_retfound.meta.json" \
  "$MEDI/models/"
cat "$MEDI/models/retinal_v8b_retfound.meta.json"

echo "=== GPU git ==="
ssh -o ConnectTimeout=20 "$SSH_HOST" bash -s <<'REMOTE'
set -euo pipefail
cd ~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare
git fetch origin main
git pull origin main || true
git add models/retinal_v8b_retfound.meta.json
if git diff --cached --quiet; then echo "GPU: nothing to commit"; else
  git commit -m "feat: retinal_v8b 완료 QWK=0.7105

- resume: v8 epoch34, lr=3e-6, batch=4
- best_val_qwk: 0.7105 (v7/v4 미달)
- 결론: v4(0.8204) 운영 유지"
fi
git push origin main
git log --oneline -3
REMOTE

echo "=== Dev MEDI git ==="
cd "$MEDI"
git pull origin main
git add models/retinal_v8b_retfound.meta.json
if git diff --cached --quiet; then echo "dev: meta unchanged"; else
  git commit -m "feat: retinal_v8b meta.json QWK=0.7105"
fi
git push origin main
git log --oneline -3

echo "OK gpu_meta_and_git"
