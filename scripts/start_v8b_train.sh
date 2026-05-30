#!/bin/bash
# v8b: v8 체크포인트에서 resume, lr 3e-6, epoch 100
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MANIFEST="${MANIFEST:-training/manifests/unified_eyeq_good.json}"
RESUME="${RESUME:-models/retinal_v8_retfound.pt}"
OUTPUT="${OUTPUT:-models/retinal_v8b_retfound.pt}"
LOG="${LOG:-/tmp/retinal_v8b_train.log}"
RESUME_EPOCH="${RESUME_EPOCH:-34}"
EPOCHS="${EPOCHS:-100}"
EARLY_STOP="${EARLY_STOP:-15}"

echo "v8b train: manifest=$MANIFEST resume=$RESUME (ep$RESUME_EPOCH) -> $OUTPUT"
echo "log: $LOG"

nohup docker run --gpus all --rm \
  --entrypoint bash \
  -v "$ROOT":/workspace \
  -v "${HOME}/workspace/dataset:/dataset:ro" \
  -v "${HOME}/.cache/torch:/root/.cache/torch" \
  medi-train:retfound -c "
    cd /workspace && python3 training/train_retfound.py \
      --manifest $MANIFEST \
      --pretrained models/pretrained/RETFound_mae_natureCFP.pth \
      --resume $RESUME \
      --resume-epoch $RESUME_EPOCH \
      --batch-size 8 \
      --epochs $EPOCHS \
      --lr 0.000003 \
      --device cuda \
      --early-stop $EARLY_STOP \
      --output $OUTPUT
  " > "$LOG" 2>&1 &

echo "v8b PID: $!"
echo "tail -f $LOG"
