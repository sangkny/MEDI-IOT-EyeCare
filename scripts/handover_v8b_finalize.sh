#!/bin/bash
# v8b 완료: Docker 재시작 + meta.json + git + 회귀 + 이미지 테스트
set -euo pipefail

PROJECTS=/mnt/e/Office_Automation/idea-collection/projects
MEDI=$PROJECTS/MEDI-IOT-EyeCare
ROOT=/mnt/e/Office_Automation/idea-collection
SSH_HOST="${SSH_HOST:-smartvisionglobal@192.168.0.23}"
GPU_REPO='~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare'

echo "=== Step 1: Docker 스택 재시작 ==="
cd "$PROJECTS"
# Stripe: .env.local 우선
set -a
[ -f .env.local ] && source .env.local
export COOPS_STRIPE_ENABLED="${COOPS_STRIPE_ENABLED:-1}"
set +a

docker compose -f docker-compose.dev.yml up -d
echo "대기 30s..."
sleep 30
docker compose -f docker-compose.dev.yml ps
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E 'medi|coops|NAMES' || true

echo "=== 헬스 체크 ==="
curl -sf http://localhost:8001/health | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('MEDI:', d.get('status'), 'model=', d.get('cnn_model','?'))
" || echo "MEDI API 미응답"

curl -sf http://localhost:8003/health | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('CoOps:', d.get('status'))
" || echo "CoOps API 미응답"

echo "=== Step 2: GPU meta.json 생성 ==="
ssh -o ConnectTimeout=20 "$SSH_HOST" bash -s <<'REMOTE'
set -euo pipefail
cd ~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare
python3 <<'PY'
import json
from datetime import datetime, timezone

meta = {
    "arch": "retfound",
    "preprocess": "none",
    "image_size": 224,
    "onnx": "retinal_v8b_retfound.onnx",
    "pt": "retinal_v8b_retfound.pt",
    "version": "train-kit-v1",
    "trained_on": "unified_eyeq_good.json",
    "epochs": 100,
    "resume_from": "retinal_v8_retfound.pt",
    "resume_epoch": 34,
    "lr": 3e-6,
    "batch_size": 4,
    "best_val_qwk": 0.7105,
    "qwk": 0.7105,
    "data_count": 13582,
    "datasets": ["eyepacs_good", "aptos", "messidor2", "idrid"],
    "created_at": datetime.now(timezone.utc).isoformat(),
    "notes": "EyeQ Good 13,582장 resume v8 ep34",
}
path = "models/retinal_v8b_retfound.meta.json"
with open(path, "w", encoding="utf-8") as f:
    json.dump(meta, f, indent=2)
print("OK meta.json QWK=", meta["best_val_qwk"])
PY
cat models/retinal_v8b_retfound.meta.json
REMOTE

echo "=== Step 3: meta.json SCP ==="
mkdir -p "$MEDI/models"
scp -o ConnectTimeout=20 \
  "${SSH_HOST}:${GPU_REPO}/models/retinal_v8b_retfound.meta.json" \
  "$MEDI/models/"
cat "$MEDI/models/retinal_v8b_retfound.meta.json"

echo "=== Step 4: GPU git push ==="
ssh -o ConnectTimeout=20 "$SSH_HOST" bash -s <<'REMOTE'
set -euo pipefail
cd ~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare
git fetch origin main
git pull --rebase origin main || git pull origin main
git add models/retinal_v8b_retfound.meta.json
if git diff --cached --quiet; then
  echo "GPU: meta.json already committed"
else
  git commit -m "feat: retinal_v8b 완료 QWK=0.7105

- resume: v8 epoch34, lr=3e-6, batch=4
- epochs: 100, EyeQ Good 13,582장
- best_val_qwk: 0.7105 (v7 0.78 미달)
- 결론: v4(0.8204) 운영 유지"
fi
git push origin main
git log --oneline -3
REMOTE

echo "=== Step 5: 개발 PC MEDI git pull ==="
cd "$MEDI"
git pull origin main
git add models/retinal_v8b_retfound.meta.json 2>/dev/null || true
if ! git diff --cached --quiet 2>/dev/null; then
  git commit -m "docs: v8b meta.json 최종 (QWK=0.7105)" || true
fi
git push origin main || true
git log --oneline -5

echo "=== Step 6: 회귀 ==="
cd "$PROJECTS"
echo "--- MEDI unit ---"
docker exec medi-iot-api-dev bash -c \
  "python -m pytest tests/ -q -m unit --tb=line 2>&1 | tail -5" || echo "MEDI unit skip"

echo "--- LLM ---"
docker exec medi-iot-api-dev bash -c \
  "export PYTHONPATH=/app/shared-libraries && python -m pytest /app/shared-libraries/llm/tests/test_providers.py -q --tb=line 2>&1 | tail -3" || echo "LLM skip"

echo "--- CoOps ---"
docker exec coops-api-dev bash -c \
  "python -m pytest tests/ -q --ignore=tests/test_stripe.py --tb=line 2>&1 | tail -3" || echo "CoOps skip"

echo "=== Step 7: 실제 이미지 ==="
cd "$MEDI"
for eye in left right; do
  echo "--- ${eye}안 ---"
  curl -sf -X POST http://localhost:8001/api/v1/lab/fundus/comprehensive \
    -F "file=@fundus_${eye}_sklee.jpg" \
    -F "lang=ko" \
    -F "include_heatmap=true" \
    -F "eye_side=${eye}" \
    | python3 -c "
import sys,json,base64,os
d=json.load(sys.stdin)
print('DR:', d.get('dr_grade'))
print('conf:', round(d.get('confidence',0),4))
print('lesion:', d.get('lesion_labels'))
print('decision:', d.get('audit_trail',{}).get('decision'))
hm=d.get('heatmap_base64','')
if hm:
    fn=f'heatmap_{eye}_latest.jpg'
    open(fn,'wb').write(base64.b64decode(hm))
    print('heatmap:', fn, os.path.getsize(fn))
" || echo "API 미응답 ${eye}"
done

echo "OK handover_v8b_finalize"
