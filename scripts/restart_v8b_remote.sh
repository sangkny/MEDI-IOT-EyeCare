#!/bin/bash
# =============================================================
# 파일명: restart_v8b_remote.sh
# 목적: restart_v8b_remote.sh 실행 스크립트
# 히스토리:
#   2026-06-11 - 현재 상태 문서화 + 히스토리 추가
# =============================================================
# GPU 서버에서 v8b 학습 재시작
set -euo pipefail
SSH_HOST="${SSH_HOST:-smartvisionglobal@192.168.0.23}"
GPU_REPO="${GPU_REPO:-~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare}"

ssh -o ConnectTimeout=15 "$SSH_HOST" bash -s <<REMOTE
set -euo pipefail
cd $GPU_REPO
if docker ps --format '{{.Names}}' | grep -qi retfound; then
  echo "retfound container already running"
  docker ps | grep -i retfound
  exit 0
fi
if [ -f scripts/start_v8b_train.sh ]; then
  bash scripts/start_v8b_train.sh
else
  echo "start_v8b_train.sh missing — inline start"
  nohup docker run --gpus all --rm --entrypoint bash \
    -v "\$(pwd)":/workspace \
    -v ~/workspace/dataset:/dataset:ro \
    -v ~/.cache/torch:/root/.cache/torch \
    medi-train:retfound -c "
      cd /workspace && python3 training/train_retfound.py \
        --manifest training/manifests/unified_eyeq_good.json \
        --pretrained models/pretrained/RETFound_mae_natureCFP.pth \
        --resume models/retinal_v8_retfound.pt \
        --resume-epoch 34 \
        --batch-size 8 --epochs 100 --lr 0.000003 \
        --device cuda --early-stop 15 \
        --output models/retinal_v8b_retfound.pt
    " > /tmp/retinal_v8b_train.log 2>&1 &
  echo "PID: \$!"
fi
sleep 3
tail -3 /tmp/retinal_v8b_train.log
REMOTE
echo "OK restart_v8b_remote"
