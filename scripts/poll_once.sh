#!/bin/bash
# =============================================================
# 파일명: poll_once.sh
# 목적: poll_once.sh 실행 스크립트
# 히스토리:
#   2026-06-11 - 현재 상태 문서화 + 히스토리 추가
# =============================================================
ssh -i ~/.ssh/id_rsa root@192.168.0.23 "grep '^epoch' /tmp/retinal_v5_train.log 2>/dev/null | tail -1"
ssh -i ~/.ssh/id_rsa root@192.168.0.23 "grep -q 'OK checkpoint' /tmp/retinal_v5_train.log 2>/dev/null" && echo TRAINING_DONE && exit 0
echo TRAINING_RUNNING
exit 1
