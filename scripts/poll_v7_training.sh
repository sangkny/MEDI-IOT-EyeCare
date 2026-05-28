#!/bin/bash
# retinal_v7_retfound 학습 완료 폴링 (10분) — QWK 게이트 + scp
set -euo pipefail

SSH="ssh -i ~/.ssh/id_rsa -o ConnectTimeout=15 root@192.168.0.23"
SCP="scp -i ~/.ssh/id_rsa"
LOG="${V7_TRAIN_LOG:-/tmp/retinal_v7_train.log}"
GPU_REPO="/home/smartvisionglobal/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare"
DEV_MODELS="/mnt/e/Office_Automation/idea-collection/projects/MEDI-IOT-EyeCare/models"
INTERVAL="${POLL_INTERVAL_SEC:-600}"

echo "v7_retfound 모니터링 ($LOG) every ${INTERVAL}s ..."

while true; do
  if $SSH "grep -q 'OK checkpoint' $LOG 2>/dev/null"; then
    echo "v7_retfound 완료 $(date -Iseconds)"
    QWK=$($SSH "cd $GPU_REPO && python3 -c \"
import json
with open('models/retinal_v7_retfound.meta.json') as f:
    m=json.load(f)
print(m.get('best_val_qwk', m.get('qwk', 0)))
\"")
    echo "QWK=$QWK"
    python3 -c "
qwk=float('$QWK')
if qwk >= 0.88:
    print('gate: clinical QWK>=0.88')
elif qwk >= 0.82:
    print('gate: deploy beats v4')
elif qwk >= 0.75:
    print('gate: deploy ok')
else:
    print('gate: keep v4')
    exit(1)
"
    mkdir -p "$DEV_MODELS"
    $SCP "root@192.168.0.23:$GPU_REPO/models/retinal_v7_retfound.onnx" "$DEV_MODELS/"
    $SCP "root@192.168.0.23:$GPU_REPO/models/retinal_v7_retfound.meta.json" "$DEV_MODELS/"
    echo "모델 전송 완료. 배포: bash scripts/post_train_v7_wsl.sh"
    exit 0
  fi

  LATEST=$($SSH "grep '^epoch' $LOG 2>/dev/null | tail -1" || true)
  echo "$(date '+%H:%M') ${LATEST:-학습 대기 중...}"
  sleep "$INTERVAL"
done
