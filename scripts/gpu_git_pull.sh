#!/bin/bash
# =============================================================
# 파일명: gpu_git_pull.sh
# 목적: gpu_git_pull.sh 실행 스크립트
# 히스토리:
#   2026-06-11 - 현재 상태 문서화 + 히스토리 추가
# =============================================================
set -euo pipefail
ssh -o ConnectTimeout=15 smartvisionglobal@192.168.0.23 bash -s <<'REMOTE'
cd ~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare
git pull origin main && echo "GPU pull OK"
REMOTE
