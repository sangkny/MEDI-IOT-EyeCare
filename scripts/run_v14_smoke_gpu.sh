#!/bin/bash
set -euo pipefail
REPO=~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare
docker run --rm --entrypoint bash --gpus all \
  -v ~/workspace/dataset:/dataset \
  -v "$REPO/data":/data_dr:ro \
  -v "$REPO":/workspace \
  medi-train:gpu -c 'cd /workspace; python3 training/train_v10.py --manifest training/manifests/unified_v14.json --pretrained models/retinal_v4.pt --output models/retinal_v14_smoke --smoke --epochs 1 --device cuda 2>&1 | tail -30'
