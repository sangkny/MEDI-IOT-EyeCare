#!/usr/bin/env bash
# AMD Phase 2 — Kaggle 데이터셋 검색·다운로드 (ADAM / iChallenge-AMD)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATASET_ROOT="${AMD_DATASET_ROOT:-$HOME/workspace/dataset/amd}"
KAGGLE_DIR="${KAGGLE_CONFIG_DIR:-$HOME/.kaggle}"

mkdir -p "$DATASET_ROOT"

echo "=== AMD 데이터셋 검색 (Kaggle) ==="
docker run --rm --entrypoint bash \
  -v "$DATASET_ROOT:/dataset" \
  -v "$KAGGLE_DIR:/root/.kaggle:ro" \
  medi-train:gpu -c "
    pip install kaggle -q 2>/dev/null || true
    echo '--- AMD macular degeneration ---'
    kaggle datasets list -s 'AMD macular degeneration' 2>/dev/null | head -15 || true
    echo '--- ADAM fundus ---'
    kaggle datasets list -s 'ADAM fundus' 2>/dev/null | head -15 || true
    echo '--- iChallenge AMD ---'
    kaggle datasets list -s 'iChallenge AMD' 2>/dev/null | head -15 || true
  " || echo "WARN: medi-train:gpu unavailable — run on GPU server"

# 알려진 데이터셋 (수동 slug — Kaggle API 토큰 필요)
ADAM_SLUG="${ADAM_KAGGLE_SLUG:-}"
ICHALLENGE_SLUG="${ICHALLENGE_AMD_SLUG:-}"

download_one() {
  local slug="$1"
  local dest="$2"
  [[ -z "$slug" ]] && return 0
  echo "=== Download $slug → $dest ==="
  docker run --rm --entrypoint bash \
    -v "$DATASET_ROOT:/dataset" \
    -v "$KAGGLE_DIR:/root/.kaggle:ro" \
    medi-train:gpu -c "
      pip install kaggle -q 2>/dev/null || true
      mkdir -p /dataset/$dest
      kaggle datasets download -d '$slug' -p /dataset/$dest --unzip
    " || echo "WARN: download failed for $slug"
}

download_one "$ADAM_SLUG" "ADAM"
download_one "$ICHALLENGE_SLUG" "iChallenge-AMD"

echo "=== Done. Dataset root: $DATASET_ROOT ==="
echo "Set ADAM_KAGGLE_SLUG / ICHALLENGE_AMD_SLUG after search, then re-run."
