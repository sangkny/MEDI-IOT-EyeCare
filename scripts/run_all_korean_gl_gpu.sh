#!/bin/bash
# 목적: 한국인 녹내장 데이터 전체 파이프라인
# IRB: 국내 임상기관 IRB 승인 (2019) — 로컬 전용
# 사용법 (GPU 서버에서 직접, 또는 WSL에서):
#   ssh gpu-smart "cd ~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare && bash scripts/run_all_korean_gl_gpu.sh"
#   bash scripts/run_all_korean_gl_gpu.sh --dry-run
set -euo pipefail
DRY=${1:-}
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
IMAGE="${TRAIN_IMAGE:-medi-train:gpu}"
DATASET="${DATASET_ROOT:-$HOME/workspace/dataset}"

echo "=== 한국인 녹내장 데이터 전처리 파이프라인 ==="
echo "IRB: 국내 임상기관 IRB 승인 (2019)"
echo "보관: GPU 서버 로컬 전용"
if [ -n "${DRY}" ]; then echo "*** DRY-RUN ***"; fi

cd "$REPO"
mkdir -p "$DATASET/korean_glaucoma_fundus"
echo '*' > "$DATASET/korean_glaucoma_fundus/.gitignore"

DOCKER_RUN="docker run --rm --entrypoint bash \
  -v $DATASET:/dataset \
  -v $REPO:/workspace \
  $IMAGE"

echo '--- Step 1: 시계열 분석 ---'
$DOCKER_RUN -c "pip install openpyxl --break-system-packages -q 2>/dev/null || true && python3 /workspace/scripts/analyze_timeseries.py"

echo '--- Step 2: 수정본 전처리 ---'
$DOCKER_RUN -c "pip install openpyxl --break-system-packages -q 2>/dev/null || true && python3 /workspace/scripts/preprocess_korean_glaucoma.py ${DRY}"

echo '--- Step 3: 원본 전처리 ---'
$DOCKER_RUN -c "pip install openpyxl --break-system-packages -q 2>/dev/null || true && python3 /workspace/scripts/preprocess_korean_gl_origin.py ${DRY}"

if [ -z "${DRY}" ]; then
  echo '--- Step 4: 시계열 라벨 생성 ---'
  $DOCKER_RUN -c "pip install openpyxl --break-system-packages -q 2>/dev/null || true && python3 /workspace/scripts/build_timeseries_labels.py"
fi

echo '--- Step 5: 품질 검증 ---'
$DOCKER_RUN -c "pip install openpyxl --break-system-packages -q 2>/dev/null || true && python3 /workspace/scripts/verify_korean_gl_output.py"

echo '=== 완료 ==='
echo "출력: $DATASET/korean_glaucoma_fundus/"
