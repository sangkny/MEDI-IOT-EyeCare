#!/bin/bash
# v8 RETFound — EyeQ Good + v4 (unified_eyeq_good.json)
set -euo pipefail

cd ~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare

nohup docker run --gpus all --rm \
  --entrypoint bash \
  -v "$(pwd)":/workspace \
  -v ~/workspace/dataset:/dataset:ro \
  -v ~/.cache/torch:/root/.cache/torch \
  medi-train:retfound -c "
    cd /workspace && python3 training/train_retfound.py \
      --manifest training/manifests/unified_eyeq_good.json \
      --pretrained models/pretrained/RETFound_mae_natureCFP.pth \
      --batch-size 8 \
      --epochs 40 \
      --lr 0.000001 \
      --device cuda \
      --early-stop 10 \
      --output models/retinal_v8_retfound.pt
  " > /tmp/retinal_v8_train.log 2>&1 &

echo "v8 PID: $!"
