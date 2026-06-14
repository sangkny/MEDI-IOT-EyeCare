#!/bin/bash
# =============================================================
# 파일명: run_kaggle_gl_download_gpu.sh
# 목적: GPU 서버 — medi-train:gpu 컨테이너에서 Kaggle GL extra2 다운로드
# 히스토리:
#   2026-06-12 - 최초 작성
# =============================================================
# 선행: ~/.kaggle/kaggle.json (GPU 호스트)
# 예: bash scripts/run_kaggle_gl_download_gpu.sh
set -euo pipefail

DATASET_ROOT="${DATASET_ROOT:-$HOME/workspace/dataset}"
IMAGE="${TRAIN_IMAGE:-medi-train:gpu}"
LOG="${LOG:-/tmp/kaggle_download.log}"

if [ ! -f "$HOME/.kaggle/kaggle.json" ]; then
  echo "FAIL: ~/.kaggle/kaggle.json 없음 — docs/GL-DATA-COLLECTION.md §3 참고"
  exit 1
fi

echo "=== Kaggle GL extra2 download (medi-train:gpu) ==="
echo "dataset: $DATASET_ROOT"
echo "log:     $LOG"

docker run --rm \
  -v "$HOME/.kaggle:/root/.kaggle:ro" \
  -v "$DATASET_ROOT:/dataset" \
  "$IMAGE" \
  bash -c '
    set -euo pipefail
    pip install kaggle --break-system-packages -q
    kaggle --version
    echo "=== G1020 ==="
    mkdir -p /dataset/Glaucoma_extra2/G1020
    kaggle datasets download -d arnavjain1/glaucoma-datasets \
      -p /dataset/Glaucoma_extra2/G1020 --unzip
    echo "=== ORIGA ==="
    mkdir -p /dataset/Glaucoma_extra2/ORIGA
    kaggle datasets download -d sshikamaru/glaucoma-detection \
      -p /dataset/Glaucoma_extra2/ORIGA --unzip
    echo "=== DRISHTI ==="
    mkdir -p /dataset/Glaucoma_extra2/DRISHTI
    kaggle datasets download -d lokeshsaipureddy/drishti-gs1 \
      -p /dataset/Glaucoma_extra2/DRISHTI --unzip
    echo "=== image count ==="
    find /dataset/Glaucoma_extra2 \( -iname "*.jpg" -o -iname "*.png" \) | wc -l
  ' 2>&1 | tee "$LOG"

echo "OK log → $LOG"
