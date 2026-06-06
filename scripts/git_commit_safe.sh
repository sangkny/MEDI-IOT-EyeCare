#!/usr/bin/env bash
# Cursor/WSL 안전 Git 커밋 — 에디터·--trailer hanging 방지
#
# 사용:
#   MSG="feat: ..." bash scripts/git_commit_safe.sh file1 file2
#   MSG="feat: ..." PUSH=1 bash scripts/git_commit_safe.sh api/lab.py
#
# 금지: git commit --trailer "Co-authored-by: ..."  (nano 무한 대기)
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ $# -lt 1 ]]; then
  echo "Usage: MSG=\"commit message\" $0 <paths...>"
  exit 2
fi

if [[ -z "${MSG:-}" ]]; then
  echo "[오류] MSG 환경변수가 필요합니다."
  exit 2
fi

export GIT_EDITOR=true
git add "$@"
git commit --no-verify -m "${MSG}"

if [[ "${PUSH:-0}" == "1" ]]; then
  git push origin main
fi

git log -1 --oneline
