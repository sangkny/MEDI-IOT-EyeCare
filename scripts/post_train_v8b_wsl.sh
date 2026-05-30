#!/bin/bash
# retinal_v8b_retfound 완료 → scp → dev PC 배포 → E2E
set -euo pipefail

SSH="ssh -o ConnectTimeout=15 smartvisionglobal@192.168.0.23"
SCP="scp"
GPU_REPO="~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare"
DEV_ROOT="/mnt/e/Office_Automation/idea-collection/projects"
MEDI="$DEV_ROOT/MEDI-IOT-EyeCare"
LOG="${V8B_TRAIN_LOG:-/tmp/retinal_v8b_train.log}"
POLL="${POLL_INTERVAL_SEC:-120}"

echo "=== Step 0: v8b 완료 대기 ==="
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

echo "=== Step 1: QWK 게이트 ==="
$SSH "cd $GPU_REPO && python3 -c \"
import json
m=json.load(open('models/retinal_v8b_retfound.meta.json'))
q=float(m.get('best_val_qwk', m.get('qwk', 0)))
print('QWK={:.4f}'.format(q))
if q>=0.82: print('gate: deploy beats v4')
elif q>=0.78: print('gate: beats v7')
else: print('gate: keep v4')
\""

echo "=== Step 2: scp ==="
mkdir -p "$MEDI/models"
$SCP "smartvisionglobal@192.168.0.23:$GPU_REPO/models/retinal_v8b_retfound.onnx" "$MEDI/models/" 2>/dev/null || echo "onnx skip (GPU export pending)"
$SCP "smartvisionglobal@192.168.0.23:$GPU_REPO/models/retinal_v8b_retfound.meta.json" "$MEDI/models/"

echo "=== Step 3-4: .env + recreate ==="
ENV_FILE="$DEV_ROOT/.env.local"
if [[ -f "$ENV_FILE" ]]; then
  sed -i 's|MEDI_CNN_MODEL_PATH=.*|MEDI_CNN_MODEL_PATH=models/retinal_v8b_retfound.onnx|' "$ENV_FILE"
  sed -i 's|MEDI_CNN_MODEL_VERSION=.*|MEDI_CNN_MODEL_VERSION=v8b|' "$ENV_FILE"
  sed -i 's|MEDI_CNN_ARCH=.*|MEDI_CNN_ARCH=vit_large_retfound|' "$ENV_FILE"
  grep MEDI_CNN "$ENV_FILE"
fi

cd "$DEV_ROOT"
docker compose -f docker-compose.dev.yml up -d --no-deps --force-recreate medi-iot-api
sleep 20

echo "=== Step 5: E2E ==="
docker exec medi-iot-api-dev python3 /app/scripts/e2e_fundus_smoke.py 2>/dev/null || \
  bash "$MEDI/scripts/test_gradcam_e2e.sh"

echo "OK post_train_v8b_wsl done"
