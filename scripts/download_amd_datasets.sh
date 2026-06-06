#!/usr/bin/env bash
# 범용 안과 AI — AMD / 근시 / 다질환 Kaggle 데이터셋 검색·다운로드
# GPU 서버(192.168.0.23)에서 실행: bash scripts/download_amd_datasets.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATASET_ROOT="${DATASET_ROOT:-$HOME/workspace/dataset}"
KAGGLE_DIR="${KAGGLE_CONFIG_DIR:-$HOME/.kaggle}"

mkdir -p "$DATASET_ROOT/AMD_raw" "$DATASET_ROOT/Myopia_raw" "$DATASET_ROOT/Multidisease_raw"

echo "=== Kaggle 데이터셋 검색 (AMD / PALM / RFMiD / ODIR) ==="
docker run --rm --entrypoint bash \
  -v "$DATASET_ROOT:/dataset" \
  -v "$KAGGLE_DIR:/root/.kaggle:ro" \
  medi-train:gpu -c "
    pip install kaggle -q 2>/dev/null || true
    mkdir -p /dataset/AMD_raw /dataset/Myopia_raw /dataset/Multidisease_raw

    echo '=== ADAM (AMD 1,200장) ==='
    kaggle datasets list -s 'ADAM macular degeneration' 2>/dev/null | head -5 || true

    echo '=== PALM (근시 1,200장) ==='
    kaggle datasets list -s 'PALM pathological myopia' 2>/dev/null | head -5 || true

    echo '=== RFMiD (다질환 3,200장 46질환) ==='
    kaggle datasets list -s 'RFMiD retinal fundus' 2>/dev/null | head -5 || true

    echo '=== ODIR (다질환 10,000장 8질환) ==='
    kaggle datasets list -s 'ODIR ocular disease' 2>/dev/null | head -5 || true
  " || echo "WARN: medi-train:gpu unavailable — run on GPU server"

# 알려진 slug (검색 후 .env 또는 환경변수로 설정)
ADAM_SLUG="${ADAM_KAGGLE_SLUG:-}"
PALM_SLUG="${PALM_KAGGLE_SLUG:-}"
RFMID_SLUG="${RFMID_KAGGLE_SLUG:-ozlemhakdagli/retinal-fundus-multi-disease-image-dataset-rfmid}"
ODIR_SLUG="${ODIR_KAGGLE_SLUG:-andrewmvd/ocular-disease-recognition}"
ICHALLENGE_AMD_SLUG="${ICHALLENGE_AMD_SLUG:-}"

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

download_one "$ADAM_SLUG" "AMD_raw/ADAM"
download_one "$ICHALLENGE_AMD_SLUG" "AMD_raw/iChallenge-AMD"
download_one "$PALM_SLUG" "Myopia_raw/PALM"
download_one "$RFMID_SLUG" "Multidisease_raw/RFMiD"
download_one "$ODIR_SLUG" "Multidisease_raw/ODIR"

echo "=== Done. Dataset root: $DATASET_ROOT ==="
echo "Manifest:"
echo "  python3 training/make_manifest.py --task amd --data-root $DATASET_ROOT --output training/manifests/amd_v1.json"
echo "  python3 training/make_manifest.py --task myopia --data-root $DATASET_ROOT --output training/manifests/myopia_v1.json"
echo "  python3 training/make_manifest.py --task multidisease --data-root $DATASET_ROOT --output training/manifests/multidisease_v1.json"
