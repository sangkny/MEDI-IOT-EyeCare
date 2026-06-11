#!/bin/bash
# =============================================================
# 파일명: post_train_v7_wsl.sh
# 목적: post_train_v7_wsl.sh 실행 스크립트
# 히스토리:
#   2026-06-11 - 현재 상태 문서화 + 히스토리 추가
# =============================================================
# retinal_v7_retfound 완료 대기 → scp → dev PC v7 배포 → E2E
set -euo pipefail

SSH="ssh -i ~/.ssh/id_rsa -o ConnectTimeout=15 root@192.168.0.23"
SCP="scp -i ~/.ssh/id_rsa"
GPU_REPO="/home/smartvisionglobal/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare"
DEV_ROOT="/mnt/e/Office_Automation/idea-collection/projects"
MEDI="$DEV_ROOT/MEDI-IOT-EyeCare"
LOG="${V7_TRAIN_LOG:-/tmp/retinal_v7_train.log}"
POLL="${POLL_INTERVAL_SEC:-120}"

echo "=== Step 0: v7 완료 대기 ==="
while true; do
  if $SSH "grep -q 'OK checkpoint' $LOG 2>/dev/null"; then
    echo "학습 완료 $(date -Iseconds)"
    $SSH "grep OK $LOG | tail -2"
    break
  fi
  line=$($SSH "grep '^epoch' $LOG 2>/dev/null | tail -1" || true)
  echo "$(date '+%H:%M:%S') ${line:-pre-epoch...}"
  sleep "$POLL"
done

echo "=== Step 1: QWK ==="
$SSH "cd $GPU_REPO && python3 -c \"
import json
m=json.load(open('models/retinal_v7_retfound.meta.json'))
q=float(m.get('best_val_qwk', m.get('qwk', 0)))
print('QWK={:.4f} arch={}'.format(q, m.get('arch')))
if q>=0.88: print('gate: clinical')
elif q>=0.82: print('gate: deploy beats v4')
elif q>=0.75: print('gate: deploy ok')
else: print('gate: review')
\""

echo "=== Step 2: scp ==="
mkdir -p "$MEDI/models"
$SCP "root@192.168.0.23:$GPU_REPO/models/retinal_v7_retfound.onnx" "$MEDI/models/"
$SCP "root@192.168.0.23:$GPU_REPO/models/retinal_v7_retfound.meta.json" "$MEDI/models/"

echo "=== Step 3-4: .env + recreate ==="
sed -i 's|MEDI_CNN_MODEL_PATH=.*|MEDI_CNN_MODEL_PATH=models/retinal_v7_retfound.onnx|' "$DEV_ROOT/.env.local"
sed -i 's|MEDI_CNN_MODEL_VERSION=.*|MEDI_CNN_MODEL_VERSION=v7|' "$DEV_ROOT/.env.local"
sed -i 's|MEDI_CNN_ARCH=.*|MEDI_CNN_ARCH=vit_large_retfound|' "$DEV_ROOT/.env.local"
grep MEDI_CNN "$DEV_ROOT/.env.local"

cd "$DEV_ROOT"
docker compose -f docker-compose.dev.yml up -d --no-deps --force-recreate medi-iot-api
sleep 18

echo "=== Step 5: E2E ==="
docker exec medi-iot-api-dev python3 /app/scripts/e2e_fundus_smoke.py

echo "OK post_train_v7_wsl done"
