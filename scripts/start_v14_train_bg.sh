#!/bin/bash
# v14 본 훈련 백그라운드 시작
set -euo pipefail
cd ~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare
nohup bash -c 'V14=1 bash scripts/start_v10_train.sh' > /tmp/v14_train.log 2>&1 &
echo "v14 training started, log: /tmp/v14_train.log"
