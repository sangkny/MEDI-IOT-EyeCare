#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
git add "$@"
MSG="${MSG:?set MSG env}"
export GIT_EDITOR=true
git commit --no-verify -m "$MSG"
git push origin main
git log -1 --oneline
