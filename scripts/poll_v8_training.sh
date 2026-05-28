#!/bin/bash
# retinal_v8_retfound 학습 완료 폴링 — QWK 게이트 + scp
set -euo pipefail

SSH="ssh -o ConnectTimeout=15 gpu-smart"
SCP="scp"
LOG="${V8_TRAIN_LOG:-/tmp/retinal_v8_train.log}"
GPU_REPO="~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare"
DEV_MODELS="/mnt/e/Office_Automation/idea-collection/projects/MEDI-IOT-EyeCare/models"
INTERVAL="${POLL_INTERVAL_SEC:-600}"

echo "v8 모니터링 시작 ($LOG) every ${INTERVAL}s ..."
while true; do
  if $SSH "grep -q 'OK checkpoint' $LOG 2>/dev/null"; then
    echo "v8 완료 $(date -Iseconds)"

    QWK=$($SSH "python3 -c \"
import json
with open('$GPU_REPO/models/retinal_v8_retfound.meta.json') as f:
    m=json.load(f)
print(m.get('best_val_qwk', m.get('qwk', 0)))
\"")
    echo "QWK=$QWK"

    python3 -c "
qwk=float('$QWK')
if qwk >= 0.85:
    print('gate: clinical QWK>=0.85')
elif qwk >= 0.82:
    print('gate: deploy beats v4')
elif qwk >= 0.78:
    print('gate: beats v7')
else:
    print('gate: keep v4')
    raise SystemExit(1)
"

    mkdir -p "$DEV_MODELS"
    $SCP "gpu-smart:$GPU_REPO/models/retinal_v8_retfound.onnx" "$DEV_MODELS/"
    $SCP "gpu-smart:$GPU_REPO/models/retinal_v8_retfound.meta.json" "$DEV_MODELS/"
    echo "모델 전송 완료. 배포: bash scripts/post_train_v8_wsl.sh"
    exit 0
  fi

  LATEST=$($SSH "grep '^epoch' $LOG 2>/dev/null | tail -1" || true)
  echo "$(date '+%H:%M') ${LATEST:-학습 대기...}"
  sleep "$INTERVAL"
done
