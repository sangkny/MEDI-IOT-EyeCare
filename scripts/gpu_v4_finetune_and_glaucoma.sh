#!/bin/bash
set -euo pipefail
SSH_HOST="${SSH_HOST:-smartvisionglobal@192.168.0.23}"
GPU_REPO=~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare

echo "=== STEP 3 GPU v4 fine-tune ==="
ssh -o ConnectTimeout=25 "$SSH_HOST" bash -s <<REMOTE
set -euo pipefail
cd ~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare
git pull origin main || echo "pull warn"
mkdir -p models/retinal_v4_ft
MANIFEST=training/manifests/unified_v4.json
if [ ! -f "\$MANIFEST" ]; then
  echo "WARN: \$MANIFEST missing on GPU — create or symlink before train"
  ls -la training/manifests/ 2>/dev/null | head -5
  exit 1
fi
nohup python3 training/train_v4_finetune.py \
  --manifest "\$MANIFEST" \
  --output models/retinal_v4_ft \
  --epochs 50 --batch-size 16 --lr 1e-4 \
  --use-clahe --use-se --mixup 0.4 \
  --resume models/retinal_v4.pt \
  > /tmp/retinal_v4_finetune.log 2>&1 &
echo "PID: \$!"
sleep 5
tail -20 /tmp/retinal_v4_finetune.log || true
REMOTE

echo "=== STEP 4 REFUGE / glaucoma manifest ==="
ssh -o ConnectTimeout=25 "$SSH_HOST" bash -s <<'REMOTE'
set -euo pipefail
mkdir -p ~/workspace/dataset/REFUGE ~/workspace/dataset/REFUGE_raw
REFUGE_COUNT=$(find ~/workspace/dataset/REFUGE ~/workspace/dataset/REFUGE_raw \
  \( -name "*.jpg" -o -name "*.png" \) 2>/dev/null | wc -l)
echo "REFUGE images found: $REFUGE_COUNT"
if [ "$REFUGE_COUNT" -lt 100 ]; then
  echo "MANUAL: https://refuge.grand-challenge.org/Download/ → ~/workspace/dataset/REFUGE_raw/"
  exit 0
fi
cd ~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare
python3 training/make_manifest.py \
  --data-root ~/workspace/dataset \
  --sources refuge \
  --output training/manifests/glaucoma_v1.json
python3 -c "
import json
m=json.load(open('training/manifests/glaucoma_v1.json'))
samples=(m.get('train') or [])+(m.get('val') or [])+(m.get('test') or [])
pos=sum(1 for s in samples if s.get('glaucoma_grade')==1)
neg=sum(1 for s in samples if s.get('glaucoma_grade')==0)
print(f'total={len(samples)} glaucoma={pos} normal={neg}')
"
REMOTE
echo "OK gpu scripts"
