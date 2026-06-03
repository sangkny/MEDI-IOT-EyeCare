#!/bin/bash
# v9 멀티태스크 학습 — GPU 서버에서 실행
set -euo pipefail

ROOT="${ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT"
LOG="${LOG:-/tmp/retinal_v9_train.log}"
DATA_ROOT="${DATA_ROOT:-$HOME/workspace/dataset}"
PRETRAINED="${PRETRAINED:-models/retinal_v4.pt}"

mkdir -p models/retinal_v9_multitask

if [[ ! -f "$PRETRAINED" && -f "models/retinal_v4.pt" ]]; then
  PRETRAINED="models/retinal_v4.pt"
fi

echo "v9 multitask → $LOG"
echo "pretrained=$PRETRAINED"

nohup docker run --gpus all --rm \
  --entrypoint bash \
  -v "$DATA_ROOT:/dataset:ro" \
  -v "$ROOT:/workspace" \
  medi-train:gpu -c "
    set -euo pipefail
    cd /workspace
    python3 training/train_multitask.py \
      --dr-manifest training/manifests/unified_v4.json \
      --glaucoma-manifest training/manifests/glaucoma_v1.json \
      --pretrained $PRETRAINED \
      --output models/retinal_v9_multitask \
      --epochs 60 \
      --batch-size 16 \
      --lr 1e-4 \
      --device cuda \
      --skip-onnx
  " > "$LOG" 2>&1 &

echo "PID: $!"
echo "tail -f $LOG"
