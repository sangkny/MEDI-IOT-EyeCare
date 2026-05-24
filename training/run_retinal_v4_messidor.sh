#!/usr/bin/env bash
# retinal_v4 — Messidor 실데이터 학습 (원격 GPU 192.168.0.23 전용)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
COMPOSE="docker compose -f training/docker-compose.train.yml"
MANIFEST="${MANIFEST:-data/messidor2_manifest.json}"

if [[ ! -f "$MANIFEST" ]]; then
  echo "ERROR: $MANIFEST 없음. data/messidor2 배치 후 manifest 생성하세요."
  echo "  see training/RETINAL_V4.md"
  exit 1
fi

echo "== build train-gpu =="
$COMPOSE build train-gpu

echo "== train retinal_v4 (Messidor) =="
ARCH="${ARCH:-efficientnet_b4}"
EPOCHS="${EPOCHS:-50}"
BATCH="${BATCH:-16}"

$COMPOSE run --rm train-gpu \
  python training/train.py \
    --manifest "$MANIFEST" \
    --arch "$ARCH" \
    --preprocess clahe \
    --epochs "$EPOCHS" \
    --batch-size "$BATCH" \
    --lr 0.0001 \
    --early-stop 5 \
    --device cuda \
    --output models/retinal_v4.pt

echo "== eval (test) =="
$COMPOSE run --rm train-gpu \
  python scripts/eval_messidor.py \
    --model models/retinal_v4.onnx \
    --manifest "$MANIFEST" \
    --split test \
    --output reports/

echo "OK retinal_v4 — scp models/retinal_v4.* to dev PC"
