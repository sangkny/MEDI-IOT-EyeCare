#!/bin/bash
# =============================================================
# 파일명: poll_v6_once.sh
# 목적: poll_v6_once.sh 실행 스크립트
# 히스토리:
#   2026-06-11 - 현재 상태 문서화 + 히스토리 추가
# =============================================================
set -euo pipefail
SSH="ssh -i ~/.ssh/id_rsa -o ConnectTimeout=10 root@192.168.0.23"
LOG="/tmp/retinal_v6_train.log"
REPO="/home/smartvisionglobal/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare"

echo "=== nvidia-smi ==="
$SSH "nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader 2>/dev/null || nvidia-smi | head -12"

echo "=== docker train ==="
$SSH "docker ps --format '{{.Names}} {{.Status}}' 2>/dev/null | grep -i train || echo NO_TRAIN_CONTAINER"

echo "=== log tail ==="
$SSH "tail -12 $LOG 2>/dev/null || echo NO_LOG"

echo "=== epochs ==="
$SSH "grep '^epoch' $LOG 2>/dev/null | tail -6 || true"

echo "=== done? ==="
if $SSH "grep -q 'OK checkpoint' $LOG 2>/dev/null"; then
  echo "TRAINING_DONE"
  $SSH "grep OK $LOG | tail -2"
  $SSH "cat $REPO/models/retinal_v6_se.meta.json 2>/dev/null || echo NO_META"
else
  echo "TRAINING_RUNNING"
fi
