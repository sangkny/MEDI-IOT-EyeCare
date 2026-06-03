#!/bin/bash
# retinal_v4_ft 학습 완료 → QWK/confidence 게이트 → 운영 전환 또는 v4 유지
set -euo pipefail

SSH="${SSH:-ssh -o ConnectTimeout=15 smartvisionglobal@192.168.0.23}"
SCP="${SCP:-scp -o ConnectTimeout=15}"
GPU_REPO="${GPU_REPO:-~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare}"
DEV_ROOT="/mnt/e/Office_Automation/idea-collection/projects"
MEDI="$DEV_ROOT/MEDI-IOT-EyeCare"
ENV_FILE="$DEV_ROOT/.env.local"
LOG="${V4_FT_LOG:-/tmp/retinal_v4_finetune.log}"
QWK_MIN="${QWK_MIN:-0.83}"
CONF_MIN="${CONF_MIN:-0.80}"

echo "=== Step 0: v4 fine-tune 완료 확인 ==="
if $SSH "grep -q 'OK checkpoint' $LOG 2>/dev/null"; then
  echo "GPU 로그에서 학습 완료 확인"
  $SSH "grep OK $LOG | tail -3" || true
else
  echo "WARN: 로그에 OK checkpoint 없음 — best.meta.json 기준으로 진행"
fi

echo "=== Step 1: QWK 게이트 (meta.json) ==="
META_LOCAL="$MEDI/models/retinal_v4_ft.best.meta.json"
mkdir -p "$MEDI/models/retinal_v4_ft"
$SCP "smartvisionglobal@192.168.0.23:$GPU_REPO/models/retinal_v4_ft/best.meta.json" "$META_LOCAL" \
  || { echo "ERROR: best.meta.json 없음"; exit 1; }

read -r QWK DEPLOY <<< "$(python3 -c "
import json
m=json.load(open('$META_LOCAL'))
q=float(m.get('best_val_qwk', m.get('qwk', 0)))
print(f'{q:.4f}', 'yes' if q>=$QWK_MIN else 'no')
")"
echo "best_val_qwk=$QWK (gate >= $QWK_MIN: $DEPLOY)"
if [[ "$DEPLOY" != "yes" ]]; then
  echo "QWK 미달 → retinal_v4 운영 유지"
  exit 1
fi

echo "=== Step 2: ONNX/PT 수신 ==="
$SCP "smartvisionglobal@192.168.0.23:$GPU_REPO/models/retinal_v4_ft/best.onnx" \
  "$MEDI/models/retinal_v4_ft.best.onnx" 2>/dev/null \
  || echo "WARN: best.onnx 없음 — GPU에서 train_v4_finetune 재실행 또는 export 필요"
$SCP "smartvisionglobal@192.168.0.23:$GPU_REPO/models/retinal_v4_ft/best.pt" \
  "$MEDI/models/retinal_v4_ft.best.pt" 2>/dev/null || true

ONNX_PATH="models/retinal_v4_ft.best.onnx"
if [[ ! -f "$MEDI/$ONNX_PATH" ]]; then
  echo "ERROR: ONNX 없어 배포 불가 — v4 유지"
  exit 1
fi

echo "=== Step 3: .env.local 업데이트 ==="
if [[ -f "$ENV_FILE" ]]; then
  sed -i "s|^MEDI_CNN_MODEL_PATH=.*|MEDI_CNN_MODEL_PATH=$ONNX_PATH|" "$ENV_FILE"
  sed -i 's|^MEDI_CNN_MODEL_VERSION=.*|MEDI_CNN_MODEL_VERSION=v4_ft|' "$ENV_FILE"
  sed -i 's|^MEDI_CNN_ARCH=.*|MEDI_CNN_ARCH=efficientnet_b4_se|' "$ENV_FILE"
  grep MEDI_CNN "$ENV_FILE" || true
fi

echo "=== Step 4: medi-iot-api 재기동 ==="
cd "$DEV_ROOT"
docker compose -f docker-compose.dev.yml up -d --no-deps --force-recreate medi-iot-api
sleep 25

echo "=== Step 5: E2E confidence 게이트 (sklee) ==="
cd "$MEDI"
CONF_OK=1
for eye in left right; do
  img="fundus_${eye}_sklee.jpg"
  if [[ ! -f "$img" ]]; then
    echo "SKIP $img"
    continue
  fi
  curl -sf -X POST "http://localhost:8001/api/v1/lab/fundus/comprehensive" \
    -F "file=@${img}" \
    -F "lang=ko" \
    -F "include_heatmap=false" \
    -F "eye_side=${eye}" \
    -o "/tmp/medi_v4ft_${eye}.json"
  if ! python3 - "$eye" "$CONF_MIN" <<'PY'
import json, sys
eye, conf_min = sys.argv[1], float(sys.argv[2])
d = json.load(open(f"/tmp/medi_v4ft_{eye}.json"))
c = float(d.get("confidence", 0))
print(f"{eye} DR={d.get('dr_grade')} conf={c:.4f}")
sys.exit(0 if c >= conf_min else 1)
PY
  then
    CONF_OK=0
  fi
done

if [[ "$CONF_OK" -ne 1 ]]; then
  echo "confidence < $CONF_MIN → v4 운영 유지 (env 롤백 권장)"
  if [[ -f "$ENV_FILE" ]]; then
    sed -i 's|^MEDI_CNN_MODEL_PATH=.*|MEDI_CNN_MODEL_PATH=models/retinal_v4.onnx|' "$ENV_FILE"
    sed -i 's|^MEDI_CNN_MODEL_VERSION=.*|MEDI_CNN_MODEL_VERSION=v4|' "$ENV_FILE"
    sed -i 's|^MEDI_CNN_ARCH=.*|MEDI_CNN_ARCH=efficientnet_b4|' "$ENV_FILE"
  fi
  docker compose -f "$DEV_ROOT/docker-compose.dev.yml" up -d --no-deps --force-recreate medi-iot-api
  exit 1
fi

echo "=== Step 6: GradCAM 스모크 (선택) ==="
bash "$MEDI/scripts/test_gradcam_e2e.sh" 2>&1 | tail -15 || true

echo "OK post_train_v4_finetune_wsl — v4_ft 운영 전환 (QWK>=$QWK_MIN, conf>=$CONF_MIN)"
