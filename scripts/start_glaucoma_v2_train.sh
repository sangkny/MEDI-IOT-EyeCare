#!/bin/bash
# Glaucoma v2 학습 — 균형 데이터 (~10,809장) · GPU 서버에서 실행
set -euo pipefail

ROOT="${ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT"
LOG="${LOG:-/tmp/retinal_glaucoma_v2_train.log}"
DATA_ROOT="${DATA_ROOT:-$HOME/workspace/dataset}"
PRETRAINED="${PRETRAINED:-models/retinal_v4.pt}"

mkdir -p models/retinal_glaucoma_v2

echo "glaucoma v2 train → $LOG"
echo "pretrained=$PRETRAINED"
echo "manifest=training/manifests/glaucoma_v2.json"

nohup docker run --gpus all --rm \
  --shm-size=4g \
  --entrypoint bash \
  -v "$DATA_ROOT:/dataset:ro" \
  -v "$ROOT:/workspace" \
  -v /tmp:/tmp \
  medi-train:gpu -c "
    set -euo pipefail
    cd /workspace
    python3 training/train_glaucoma.py \
      --manifest training/manifests/glaucoma_v2.json \
      --pretrained $PRETRAINED \
      --output models/retinal_glaucoma_v2 \
      --epochs 80 \
      --batch-size 64 \
      --lr 1e-4 \
      --focal-gamma 2.0 \
      --focal-alpha 0.5 \
      --early-stop 15 \
      --device cuda \
      2>&1 | tee /tmp/retinal_glaucoma_v2_train.log
  " > "$LOG" 2>&1 &

echo "PID: $!"
echo "tail -f $LOG"
echo "tail -f /tmp/retinal_glaucoma_v2_train.log  # container tee (host /tmp mount)"
