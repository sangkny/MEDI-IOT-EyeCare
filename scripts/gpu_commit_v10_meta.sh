#!/usr/bin/env bash
# =============================================================
# 파일명: gpu_commit_v10_meta.sh
# 목적: gpu_commit_v10_meta.sh 실행 스크립트
# 히스토리:
#   2026-06-11 - 현재 상태 문서화 + 히스토리 추가
# =============================================================
set -euo pipefail
cd /home/smartvisionglobal/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare
git add models/retinal_v10c/best.meta.json models/retinal_v10b/best.meta.json
printf '%s\n' 'docs: v10b v10c GPU training meta' > /tmp/medi_gpu_commitmsg
git commit -F /tmp/medi_gpu_commitmsg
git push
