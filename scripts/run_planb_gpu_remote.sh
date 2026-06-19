#!/bin/bash
# GPU repo sync + Plan B build
set -euo pipefail
REPO="${REPO:-$HOME/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare}"
cd "$REPO"
if ! git pull; then
  echo "WARN: git pull failed — trying sudo"
  sudo git pull
fi
bash scripts/run_build_v13_planb_gpu.sh
