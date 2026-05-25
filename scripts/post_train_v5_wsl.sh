#!/bin/bash
# retinal_v5 학습 완료 대기 → QWK 게이트 → scp → dev PC 배포 → E2E
# WSL: bash scripts/post_train_v5_wsl.sh
set -euo pipefail

SSH="ssh -i ~/.ssh/id_rsa -o ConnectTimeout=15 root@192.168.0.23"
SCP="scp -i ~/.ssh/id_rsa"
GPU_REPO="/home/smartvisionglobal/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare"
DEV_ROOT="/mnt/e/Office_Automation/idea-collection/projects"
MEDI="$DEV_ROOT/MEDI-IOT-EyeCare"
LOG="/tmp/retinal_v5_train.log"
POLL="${POLL_INTERVAL_SEC:-120}"

echo "=== Step 0: 학습 완료 대기 ==="
while true; do
  if $SSH "grep -q 'OK checkpoint' $LOG 2>/dev/null"; then
    echo "학습 완료"
    $SSH "grep -E 'OK checkpoint|best_val_qwk|^epoch' $LOG | tail -6"
    break
  fi
  line=$($SSH "grep '^epoch' $LOG 2>/dev/null | tail -1" || true)
  echo "$(date '+%H:%M:%S') ${line:-waiting...}"
  sleep "$POLL"
done

echo "=== Step 1: QWK 게이트 ==="
$SSH "cd $GPU_REPO && python3 - <<'PY'
import json
with open('models/retinal_v5.meta.json') as f:
    meta = json.load(f)
qwk = float(meta.get('best_val_qwk', meta.get('qwk', 0)))
print(f'QWK: {qwk:.4f} arch={meta.get(\"arch\")}')
if qwk >= 0.85:
    print('gate: clinical target')
elif qwk >= 0.80:
    print('gate: deploy ok')
else:
    print('gate: warn consider v5_clahe')
PY"

echo "=== Step 2: scp → dev PC ==="
mkdir -p "$MEDI/models"
$SCP "root@192.168.0.23:$GPU_REPO/models/retinal_v5.onnx" "$MEDI/models/"
$SCP "root@192.168.0.23:$GPU_REPO/models/retinal_v5.meta.json" "$MEDI/models/"
$SCP "root@192.168.0.23:$GPU_REPO/training/train.py" "$MEDI/training/"

echo "=== Step 3–4: .env.local + compose ==="
sed -i 's|MEDI_CNN_MODEL_PATH=.*|MEDI_CNN_MODEL_PATH=models/retinal_v5.onnx|' "$DEV_ROOT/.env.local"
sed -i 's|MEDI_CNN_MODEL_VERSION=.*|MEDI_CNN_MODEL_VERSION=v5|' "$DEV_ROOT/.env.local"
grep MEDI_CNN "$DEV_ROOT/.env.local"

cd "$DEV_ROOT"
docker compose -f docker-compose.dev.yml up -d medi-iot-api
sleep 20

echo "=== Step 5–6: ONNX + E2E ==="
docker exec medi-iot-api-dev python3 /app/scripts/e2e_fundus_smoke.py

echo "=== Step 11: v4 vs v5 ONNX ==="
docker exec medi-iot-api-dev python3 - <<'PY'
import json, onnxruntime as ort, numpy as np, torch
for v, mp, jp in [
    ("v4","models/retinal_v4.onnx","models/retinal_v4.meta.json"),
    ("v5","models/retinal_v5.onnx","models/retinal_v5.meta.json"),
]:
    meta = json.load(open(jp))
    out = ort.InferenceSession(mp, providers=["CPUExecutionProvider"]).run(
        None, {"input": np.random.randn(1,3,224,224).astype(np.float32)})[0][0]
    p = torch.softmax(torch.tensor(out), 0).numpy()
    print(v, "qwk=", meta.get("best_val_qwk", meta.get("qwk")),
          "conf=", f"{p.max():.4f}")
PY

echo "OK post_train_v5_wsl done"
