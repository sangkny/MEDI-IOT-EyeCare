#!/bin/bash
# GPU 서버: medi-train:gpu 컨테이너에서 v4 fine-tune
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LOG="${LOG:-/tmp/retinal_v4_finetune.log}"
MANIFEST="${MANIFEST:-training/manifests/unified_v4.json}"

if [[ ! -f "$MANIFEST" ]]; then
  echo "ERROR: manifest missing: $MANIFEST"
  exit 1
fi

nohup docker run --gpus all --rm \
  --entrypoint bash \
  -v "$ROOT":/workspace \
  -v "${HOME}/workspace/dataset:/dataset:ro" \
  medi-train:gpu -c "
    cd /workspace && python3 training/train_v4_finetune.py \
      --manifest $MANIFEST \
      --output models/retinal_v4_ft \
      --epochs 50 --batch-size 16 --lr 1e-4 \
      --use-clahe --use-se --mixup 0.4 \
      --resume models/retinal_v4.pt \
      --device cuda
  " > "$LOG" 2>&1 &

echo "v4_finetune PID: $!"
echo "tail -f $LOG"
