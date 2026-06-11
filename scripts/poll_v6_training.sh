#!/bin/bash
# =============================================================
# 파일명: poll_v6_training.sh
# 목적: poll_v6_training.sh 실행 스크립트
# 히스토리:
#   2026-06-11 - 현재 상태 문서화 + 히스토리 추가
# =============================================================
# retinal_v6_se 학습 완료 폴링 (10분 간격) — 완료 시 QWK 게이트 + scp 안내
set -euo pipefail

SSH="ssh -i ~/.ssh/id_rsa -o ConnectTimeout=15 root@192.168.0.23"
LOG="${V6_TRAIN_LOG:-/tmp/retinal_v6c_train.log}"
REPO="/home/smartvisionglobal/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare"
INTERVAL="${POLL_INTERVAL_SEC:-600}"

echo "Polling v6_se ($LOG) every ${INTERVAL}s ..."

while true; do
  if $SSH "grep -q 'OK checkpoint' $LOG 2>/dev/null"; then
    QWK=$($SSH "python3 -c \"
import json
with open('$REPO/models/retinal_v6_se.meta.json') as f:
    m=json.load(f)
print(m.get('best_val_qwk', m.get('qwk', 0)))
\"")
    echo "✅ v6_se 완료! QWK=$QWK"
    python3 -c "
qwk=float('$QWK')
if qwk >= 0.75:
    print(f'🎉 QWK={qwk} → v6_se 배포 권장 (post_train_v6_wsl.sh)')
elif qwk >= 0.50:
    print(f'✅ QWK={qwk} → v4 대비 검토 후 배포')
else:
    print(f'⚠️  QWK={qwk} → v4 유지 권장')
"
    echo "배포: bash scripts/post_train_v6_wsl.sh"
    exit 0
  fi

  LATEST=$($SSH "grep '^epoch' $LOG 2>/dev/null | tail -1" || true)
  echo "$(date '+%H:%M') ${LATEST:-pre-epoch...}"
  sleep "$INTERVAL"
done
