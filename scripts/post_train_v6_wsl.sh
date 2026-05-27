#!/bin/bash
# retinal_v6_se 학습 완료 대기 → scp → dev PC v6 배포 → E2E
set -euo pipefail

SSH="ssh -i ~/.ssh/id_rsa -o ConnectTimeout=15 root@192.168.0.23"
SCP="scp -i ~/.ssh/id_rsa"
GPU_REPO="/home/smartvisionglobal/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare"
DEV_ROOT="/mnt/e/Office_Automation/idea-collection/projects"
MEDI="$DEV_ROOT/MEDI-IOT-EyeCare"
LOG="${V6_TRAIN_LOG:-/tmp/retinal_v6c_train.log}"
POLL="${POLL_INTERVAL_SEC:-120}"

echo "=== Step 0: v6_se 완료 대기 ==="
while true; do
  if $SSH "grep -q 'OK checkpoint' $LOG 2>/dev/null"; then
    echo "학습 완료 $(date -Iseconds)"
    $SSH "grep OK $LOG | tail -2"
    break
  fi
  line=$($SSH "grep '^epoch' $LOG 2>/dev/null | tail -1" || true)
  echo "$(date '+%H:%M:%S') ${line:-pre-epoch (download/setup)...}"
  sleep "$POLL"
done

echo "=== Step 1: QWK ==="
$SSH "cd $GPU_REPO && python3 -c \"
import json
m=json.load(open('models/retinal_v6_se.meta.json'))
q=float(m.get('best_val_qwk', m.get('qwk', 0)))
print('QWK={:.4f} arch={}'.format(q, m.get('arch')))
if q>=0.85: print('gate: clinical')
elif q>=0.75: print('gate: deploy ok')
elif q>=0.80: print('gate: ok')
else: print('gate: review')
\""

echo "=== Step 2: scp ==="
# medi-iot-api 컨테이너는 ./MEDI-IOT-EyeCare 를 /app 으로 마운트한다.
# 따라서 `.env.local` 의 `MEDI_CNN_MODEL_PATH=models/...` 는 /app/models 를 의미한다.
mkdir -p "$MEDI/models"
$SCP "root@192.168.0.23:$GPU_REPO/models/retinal_v6_se.onnx" "$MEDI/models/"
$SCP "root@192.168.0.23:$GPU_REPO/models/retinal_v6_se.meta.json" "$MEDI/models/"

echo "=== Step 3-4: .env + restart ==="
sed -i 's|MEDI_CNN_MODEL_PATH=.*|MEDI_CNN_MODEL_PATH=models/retinal_v6_se.onnx|' "$DEV_ROOT/.env.local"
sed -i 's|MEDI_CNN_MODEL_VERSION=.*|MEDI_CNN_MODEL_VERSION=v6|' "$DEV_ROOT/.env.local"
sed -i 's|MEDI_CNN_ARCH=.*|MEDI_CNN_ARCH=efficientnet_b4_se|' "$DEV_ROOT/.env.local"
grep MEDI_CNN "$DEV_ROOT/.env.local"

cd "$DEV_ROOT"
# env_file 변경이 restart 로는 반영되지 않을 수 있어 강제 recreate 한다.
docker compose -f docker-compose.dev.yml up -d --no-deps --force-recreate medi-iot-api
sleep 18

echo "=== Step 5: E2E ==="
docker exec medi-iot-api-dev python3 /app/scripts/e2e_fundus_smoke.py

echo "OK post_train_v6_wsl done"
