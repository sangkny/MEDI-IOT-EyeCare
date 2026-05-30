#!/bin/bash
set -euo pipefail
SSH_HOST="${SSH_HOST:-smartvisionglobal@192.168.0.23}"
ssh -o ConnectTimeout=15 "$SSH_HOST" bash -s <<'REMOTE'
LOG=/tmp/retinal_v8b_train.log
echo "=== tail log ==="
tail -8 "$LOG" 2>/dev/null || echo "(no log)"
echo "=== epochs ==="
grep -E '^epoch [0-9]' "$LOG" 2>/dev/null | tail -8 || echo "(no epoch lines yet)"
echo "=== gpu procs ==="
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv 2>/dev/null || true
echo "=== util/mem ==="
nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader
echo "=== train ps ==="
ps aux | grep -E 'train_retfound|retinal_v8' | grep -v grep || echo "(no train ps)"
REMOTE
