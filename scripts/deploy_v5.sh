#!/bin/bash
# =============================================================
# 파일명: deploy_v5.sh
# 목적: deploy_v5.sh 실행 스크립트
# 히스토리:
#   2026-06-11 - 현재 상태 문서화 + 히스토리 추가
# =============================================================
# retinal_v5 학습 완료 후 개발 PC 배포 (GPU 서버 192.168.0.23 에서 실행)
#
#   bash scripts/deploy_v5.sh
#   bash scripts/deploy_v5.sh --help

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/deploy_v5.sh

GPU 서버에서 retinal_v5.onnx/meta.json 을 개발 PC로 scp 하고,
meta.json 만 git push 한 뒤 개발 PC API 를 v5 로 재시작합니다.

전제:
  - models/retinal_v5.onnx, models/retinal_v5.meta.json 존재
  - 개발 PC SSH: DEV_PC (기본 root@192.168.0.12)
  - 개발 PC 경로: DEV_PATH (기본 .../MEDI-IOT-EyeCare/models)

환경변수:
  DEV_PC, DEV_PATH, REPO
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

REPO="${REPO:-/home/smartvisionglobal/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare}"
DEV_PC="${DEV_PC:-root@192.168.0.12}"
GPU_HOST="${GPU_HOST:-root@192.168.0.23}"
SCP_ID="${SCP_ID:-$HOME/.ssh/id_rsa}"
DEV_PATH="${DEV_PATH:-/mnt/e/Office_Automation/idea-collection/projects/MEDI-IOT-EyeCare/models}"

cd "$REPO"

for f in models/retinal_v5.onnx models/retinal_v5.meta.json; do
  if [[ ! -f "$f" ]]; then
    echo "missing: $f — 학습 완료 후 다시 실행하세요." >&2
    exit 1
  fi
done

QWK=$(python3 -c "
import json
with open('models/retinal_v5.meta.json') as f:
    m = json.load(f)
print(m.get('best_val_qwk', m.get('qwk', 0)))
")
echo "QWK: $QWK"

python3 -c "
qwk = float('$QWK')
if qwk < 0.80:
    print(f'warn QWK={qwk} < 0.80 — 배포 주의')
elif qwk >= 0.85:
    print(f'OK QWK={qwk} >= 0.85 — 임상 목표 달성')
else:
    print(f'OK QWK={qwk} — 배포 가능')
"

scp models/retinal_v5.onnx "$DEV_PC:$DEV_PATH/"
scp models/retinal_v5.meta.json "$DEV_PC:$DEV_PATH/"
echo "OK model scp → $DEV_PC:$DEV_PATH/"

git add models/retinal_v5.meta.json
if git diff --cached --quiet; then
  echo "skip git commit (meta.json unchanged)"
else
  git commit -m "feat: retinal_v5 학습 완료 (EyePACS 포함, QWK=$QWK)"
  git push
  echo "OK git push meta.json"
fi

ssh "$DEV_PC" <<DEVEOF
set -e
cd /mnt/e/Office_Automation/idea-collection/projects
sed -i 's|MEDI_CNN_MODEL_PATH=.*|MEDI_CNN_MODEL_PATH=models/retinal_v5.onnx|' .env.local
sed -i 's|MEDI_CNN_MODEL_VERSION=.*|MEDI_CNN_MODEL_VERSION=v5|' .env.local
docker compose -f docker-compose.dev.yml restart medi-iot-api
sleep 15
docker exec medi-iot-api-dev python3 /app/scripts/e2e_fundus_smoke.py
DEVEOF

echo "OK deploy_v5 complete"
