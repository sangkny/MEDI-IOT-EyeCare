#!/usr/bin/env bash
# =============================================================
# 파일명: git_commit_safe.sh
# 목적: GIT_EDITOR=true 안전 커밋 (WSL nano hang 방지)
# 히스토리:
#   2026-06-11 - 현재 상태 문서화 + 히스토리 추가
# =============================================================
# MEDI-IOT-EyeCare — Cursor/WSL 안전 커밋 (nano hang 방지)
# Usage:
#   MSG="fix: ..." bash scripts/git_commit_safe.sh training/train_v10.py
#   MSG_FILE=/tmp/msg.txt bash scripts/git_commit_safe.sh file1 file2
#   PUSH=1 MSG="..." bash scripts/git_commit_safe.sh ...
set -euo pipefail
cd "$(dirname "$0")/.."
[[ $# -ge 1 ]] || { echo "Usage: MSG=\"...\" $0 <files...>"; exit 2; }

export GIT_EDITOR=true
export GIT_SEQUENCE_EDITOR=true

git add "$@"

if [[ -n "${MSG_FILE:-}" ]]; then
  git commit --no-verify -F "${MSG_FILE}"
elif [[ -n "${MSG:-}" ]]; then
  git commit --no-verify -m "${MSG}"
else
  echo "[오류] MSG 또는 MSG_FILE 필요"; exit 2
fi

[[ "${PUSH:-0}" == "1" ]] && git push origin main
git log -1 --oneline
