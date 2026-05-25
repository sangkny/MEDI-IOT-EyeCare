#!/bin/bash
# GPU 서버 retinal_v5 학습 완료 대기 (WSL에서 실행)
set -euo pipefail

SSH="ssh -i ~/.ssh/id_rsa -o ConnectTimeout=10 root@192.168.0.23"
REPO="/home/smartvisionglobal/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare"
LOG="/tmp/retinal_v5_train.log"
INTERVAL="${POLL_INTERVAL_SEC:-120}"

echo "Polling $LOG every ${INTERVAL}s ..."

while true; do
  if $SSH "grep -q 'OK checkpoint' $LOG 2>/dev/null"; then
    echo "DONE at $(date -Iseconds)"
    $SSH "grep -E 'OK checkpoint|best_val_qwk|^epoch' $LOG | tail -8"
    exit 0
  fi
  line=$($SSH "grep '^epoch' $LOG 2>/dev/null | tail -1" || true)
  echo "$(date '+%H:%M:%S') training: ${line:-no epoch line yet}"
  sleep "$INTERVAL"
done
