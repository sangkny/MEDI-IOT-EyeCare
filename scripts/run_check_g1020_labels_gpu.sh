#!/bin/bash
# G1020 json 라벨 구조 확인 (GPU 1회)
set -euo pipefail
docker run --rm --entrypoint python3 \
  -v ~/workspace/dataset:/dataset \
  -v ~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare:/workspace \
  medi-train:gpu \
  /workspace/scripts/check_g1020_labels.py
