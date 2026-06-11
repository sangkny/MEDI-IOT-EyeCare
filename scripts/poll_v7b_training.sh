#!/bin/bash
# =============================================================
# 파일명: poll_v7b_training.sh
# 목적: poll_v7b_training.sh 실행 스크립트
# 히스토리:
#   2026-06-11 - 현재 상태 문서화 + 히스토리 추가
# =============================================================
set -euo pipefail

SSH="ssh -o ConnectTimeout=15 gpu-smart"
SCP="scp"
LOG="${V7B_TRAIN_LOG:-/tmp/retinal_v7b_train.log}"
GPU_REPO="~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare"
DEV_MODELS="/mnt/e/Office_Automation/idea-collection/projects/MEDI-IOT-EyeCare/models"
INTERVAL="${POLL_INTERVAL_SEC:-600}"

echo "v7b 모니터링 시작... ($LOG) every ${INTERVAL}s"
while true; do
  if $SSH "grep -q 'OK checkpoint' $LOG 2>/dev/null"; then
    echo "✅ v7b 완료! $(date -Iseconds)"

    QWK=$($SSH "python3 -c \"
import json
with open('$GPU_REPO/models/retinal_v7b_retfound.meta.json') as f:
    m=json.load(f)
print(m.get('best_val_qwk', m.get('qwk', 0)))
\"")
    echo "QWK=$QWK"

    python3 -c "
qwk=float('$QWK')
if qwk >= 0.82:
    print('gate: v4 대비 향상')
elif qwk >= 0.78:
    print('gate: v7 대비 향상')
else:
    print('gate: v7 유지')
    raise SystemExit(1)
"

    mkdir -p "$DEV_MODELS"
    $SCP "gpu-smart:$GPU_REPO/models/retinal_v7b_retfound.onnx" "$DEV_MODELS/"
    $SCP "gpu-smart:$GPU_REPO/models/retinal_v7b_retfound.meta.json" "$DEV_MODELS/"
    echo "✅ 전송 완료"
    exit 0
  fi

  LATEST=$($SSH "grep '^epoch' $LOG 2>/dev/null | tail -1" || true)
  echo "$(date '+%H:%M') ${LATEST:-학습 대기...}"
  sleep "$INTERVAL"
done

