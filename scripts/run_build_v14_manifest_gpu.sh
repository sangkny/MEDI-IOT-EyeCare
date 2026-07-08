#!/bin/bash
set -euo pipefail
REPO=~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare
cd "$REPO"
git pull
docker run --rm --entrypoint bash \
  -v ~/workspace/dataset:/dataset \
  -v "$REPO":/workspace \
  medi-train:gpu -c 'pip install openpyxl --break-system-packages -q; python3 /workspace/scripts/build_v14_manifest.py'
