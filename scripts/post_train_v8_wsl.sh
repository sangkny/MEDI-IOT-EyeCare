#!/bin/bash
# retinal_v8_retfound 완료 대기 → scp → dev PC v8 배포 → E2E
set -euo pipefail

SSH="ssh -o ConnectTimeout=15 gpu-smart"
SCP="scp"
GPU_REPO="~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare"
DEV_ROOT="/mnt/e/Office_Automation/idea-collection/projects"
MEDI="$DEV_ROOT/MEDI-IOT-EyeCare"
LOG="${V8_TRAIN_LOG:-/tmp/retinal_v8_train.log}"
POLL="${POLL_INTERVAL_SEC:-120}"

echo "=== Step 0: v8 완료 대기 ==="
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
m=json.load(open('models/retinal_v8_retfound.meta.json'))
q=float(m.get('best_val_qwk', m.get('qwk', 0)))
print('QWK={:.4f}'.format(q))
if q>=0.85: print('gate: clinical')
elif q>=0.82: print('gate: deploy beats v4')
elif q>=0.78: print('gate: beats v7')
else: print('gate: review')
\""

echo "=== Step 2: scp (없으면 GPU에서 pull) ==="
mkdir -p "$MEDI/models"
if $SSH "test -f $GPU_REPO/models/retinal_v8_retfound.onnx"; then
  $SCP "gpu-smart:$GPU_REPO/models/retinal_v8_retfound.onnx" "$MEDI/models/"
  $SCP "gpu-smart:$GPU_REPO/models/retinal_v8_retfound.meta.json" "$MEDI/models/"
else
  echo "GPU onnx 없음 — 로컬 models 확인"
fi

echo "=== Step 3-4: .env + recreate ==="
sed -i 's|MEDI_CNN_MODEL_PATH=.*|MEDI_CNN_MODEL_PATH=models/retinal_v8_retfound.onnx|' "$DEV_ROOT/.env.local"
sed -i 's|MEDI_CNN_MODEL_VERSION=.*|MEDI_CNN_MODEL_VERSION=v8|' "$DEV_ROOT/.env.local"
sed -i 's|MEDI_CNN_ARCH=.*|MEDI_CNN_ARCH=vit_large_retfound|' "$DEV_ROOT/.env.local"
grep MEDI_CNN "$DEV_ROOT/.env.local"

cd "$DEV_ROOT"
docker compose -f docker-compose.dev.yml up -d --no-deps --force-recreate medi-iot-api
sleep 20

echo "=== Step 5: E2E ==="
docker exec medi-iot-api-dev python3 /app/scripts/e2e_fundus_smoke.py

echo "OK post_train_v8_wsl done"
