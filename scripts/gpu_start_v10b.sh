#!/bin/bash
# =============================================================
# 파일명: gpu_start_v10b.sh
# 목적: gpu_start_v10b.sh 실행 스크립트
# 히스토리:
#   2026-06-11 - 현재 상태 문서화 + 히스토리 추가
# =============================================================
# GPU v10b 재훈련 시작 (백그라운드 nohup)
set -euo pipefail

REPO="${REPO:-$HOME/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare}"
cd "$REPO"

if docker ps -q --filter ancestor=medi-train:gpu | grep -q .; then
  echo "FAIL: medi-train:gpu container already running"
  docker ps --filter ancestor=medi-train:gpu
  exit 1
fi

git pull || echo "WARN: git pull failed — continue with local tree"

nohup env V10B=1 bash scripts/start_v10_train.sh > /tmp/v10b_train.nohup.log 2>&1 &
echo "PID=$!"
sleep 5
docker ps --filter ancestor=medi-train:gpu || true
tail -5 /tmp/v10b_train.nohup.log 2>/dev/null || true
