#!/usr/bin/env bash
# 원클릭: 데이터 준비 → GPU 학습 → eval
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
COMPOSE="docker compose -f training/docker-compose.train.yml"

MODE="${1:-gpu}"
ARCH="${ARCH:-efficientnet_b4}"
EPOCHS="${EPOCHS:-50}"

echo "== build =="
$COMPOSE build "train-${MODE}"

echo "== data prep =="
$COMPOSE run --rm data-prep

echo "== train (${MODE}) =="
ARCH="$ARCH" EPOCHS="$EPOCHS" $COMPOSE run --rm "train-${MODE}"

echo "== eval =="
$COMPOSE --profile eval run --rm eval-gpu 2>/dev/null || \
  python3 scripts/eval_messidor.py \
    --model models/retinal_v3.onnx \
    --manifest data/synthetic_manifest.json \
    --split test \
    --output reports/

echo "== deploy hint =="
python3 training/deploy_model.py --model retinal_v3.onnx --target print
