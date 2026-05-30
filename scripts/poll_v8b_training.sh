#!/bin/bash
# retinal_v8b_retfound 학습 완료 폴링 — QWK 게이트 + scp
set -euo pipefail

SSH="ssh -o ConnectTimeout=15 smartvisionglobal@192.168.0.23"
SCP="scp"
LOG="${V8B_TRAIN_LOG:-/tmp/retinal_v8b_train.log}"
GPU_REPO="~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare"
DEV_MODELS="/mnt/e/Office_Automation/idea-collection/projects/MEDI-IOT-EyeCare/models"
INTERVAL="${POLL_INTERVAL_SEC:-600}"

echo "v8b 모니터링 시작 ($LOG) every ${INTERVAL}s ..."
while true; do
  if $SSH "grep -q 'OK checkpoint' $LOG 2>/dev/null"; then
    echo "✅ v8b 완료 $(date -Iseconds)"

    QWK=$($SSH "python3 -c \"
import json
with open('$GPU_REPO/models/retinal_v8b_retfound.meta.json') as f:
    m=json.load(f)
print(m.get('best_val_qwk', m.get('qwk', 0)))
\"")
    echo "v8b QWK=$QWK"

    python3 -c "
qwk=float('$QWK')
if qwk >= 0.85:
    print('🎉 임상 목표 QWK≥0.85 달성!')
elif qwk >= 0.82:
    print('✅ v4(0.8204) 대비 향상 → 배포!')
elif qwk >= 0.78:
    print('✅ v7(0.78) 역전 → 배포!')
else:
    print(f'⚠️  QWK={qwk} → v4 유지')
    raise SystemExit(1)
"

    mkdir -p "$DEV_MODELS"
    $SCP "smartvisionglobal@192.168.0.23:$GPU_REPO/models/retinal_v8b_retfound.onnx" "$DEV_MODELS/" 2>/dev/null || true
    $SCP "smartvisionglobal@192.168.0.23:$GPU_REPO/models/retinal_v8b_retfound.meta.json" "$DEV_MODELS/"
    echo "✅ 전송 완료 → bash scripts/post_train_v8b_wsl.sh"
    exit 0
  fi

  LATEST=$($SSH "grep -E '^epoch [0-9]' $LOG 2>/dev/null | tail -1" || true)
  echo "$(date '+%H:%M') ${LATEST:-v8b 대기...}"
  sleep "$INTERVAL"
done
