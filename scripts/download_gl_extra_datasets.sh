#!/bin/bash
# =============================================================
# 파일명: download_gl_extra_datasets.sh
# 목적: GL AUC 개선을 위한 추가 공개 녹내장 데이터셋 수집
# 히스토리:
#   2026-06-12 - 최초 작성 (v10d 결과 후 데이터 증가 전략)
# =============================================================
# 대상 (~2,971장 추가 목표):
#   REFUGE  (~1,200) https://refuge.grand-challenge.org
#   G1020   (~1,020) Kaggle: arnavjain1/glaucoma-datasets
#   ORIGA   (~650)   Kaggle: sshikamaru/glaucoma-detection
#   DRISHTI (~101)   Kaggle: oneeyeopen/drishti-gs-retina-dataset-for-glaucoma-detection
#
# 출력: $DATASET_ROOT/Glaucoma_extra2/{REFUGE,G1020,ORIGA,DRISHTI}/
# 전처리: scripts/preprocess_all.py → resized_cache/Glaucoma_extra2/
#
# 예:
#   export KAGGLE_USERNAME=... KAGGLE_KEY=...
#   bash scripts/download_gl_extra_datasets.sh
#   bash scripts/download_gl_extra_datasets.sh --dry-run
set -euo pipefail

REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
DATASET_ROOT="${DATASET_ROOT:-$HOME/workspace/dataset}"
OUT_ROOT="${OUT_ROOT:-$DATASET_ROOT/Glaucoma_extra2}"
DRY_RUN=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --help|-h)
      sed -n '1,22p' "$0"
      exit 0
      ;;
  esac
done

log() { echo "[download_gl_extra] $*"; }
run() {
  if [ "$DRY_RUN" = "1" ]; then
    log "DRY-RUN: $*"
  else
    log "RUN: $*"
    eval "$@"
  fi
}

mkdir -p "$OUT_ROOT"/{REFUGE,G1020,ORIGA,DRISHTI}

# ── Kaggle CLI ───────────────────────────────────────────────
if ! command -v kaggle >/dev/null 2>&1; then
  log "WARN: kaggle CLI 없음 — pip install kaggle 후 ~/.kaggle/kaggle.json 설정"
  log "      https://www.kaggle.com/docs/api#authentication"
fi

_kaggle_download() {
  local slug="$1"
  local dest="$2"
  if [ ! -f "$HOME/.kaggle/kaggle.json" ] && [ -z "${KAGGLE_USERNAME:-}" ]; then
    log "SKIP $slug — Kaggle 인증 없음 ($dest)"
    return 0
  fi
  mkdir -p "$dest"
  run "kaggle datasets download -d '$slug' -p '$dest' --unzip"
}

# ── G1020 ────────────────────────────────────────────────────
log "=== G1020 (~1,020) ==="
_kaggle_download "arnavjain1/glaucoma-datasets" "$OUT_ROOT/G1020"

# ── ORIGA ────────────────────────────────────────────────────
log "=== ORIGA (~650) ==="
_kaggle_download "sshikamaru/glaucoma-detection" "$OUT_ROOT/ORIGA"

# ── DRISHTI-GS ───────────────────────────────────────────────
log "=== DRISHTI-GS (~101) ==="
_kaggle_download "oneeyeopen/drishti-gs-retina-dataset-for-glaucoma-detection" "$OUT_ROOT/DRISHTI"
# GPU 권장 slug (run_kaggle_gl_download_gpu.sh):
#   lokeshsaipureddy/drishti-gs1

# ── REFUGE (수동) ────────────────────────────────────────────
log "=== REFUGE (~1,200) — 수동 다운로드 필요 ==="
REFUGE_DIR="$OUT_ROOT/REFUGE"
if [ -d "$REFUGE_DIR/Images" ] || [ -d "$REFUGE_DIR/Training400" ]; then
  log "REFUGE 이미 존재: $REFUGE_DIR"
else
  cat <<EOF
REFUGE는 Grand-Challenge 등록 후 수동 다운로드:
  1. https://refuge.grand-challenge.org 접속 · 계정 생성
  2. REFUGE1 / REFUGE2 데이터 다운로드
  3. 압축 해제 후 아래 경로에 배치:
       $REFUGE_DIR/
     (Images/ 또는 Training400/ + Glaucoma_label/ 등 하위 구조 유지)
  4. 재실행: bash scripts/download_gl_extra_datasets.sh
EOF
fi

# ── 요약 ─────────────────────────────────────────────────────
count_images() {
  local dir="$1"
  if [ ! -d "$dir" ]; then
    echo 0
    return
  fi
  find "$dir" -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.bmp' -o -iname '*.tif' -o -iname '*.tiff' \) 2>/dev/null | wc -l | tr -d ' '
}

log "=== 수집 현황 ($OUT_ROOT) ==="
for name in REFUGE G1020 ORIGA DRISHTI; do
  n=$(count_images "$OUT_ROOT/$name")
  log "  $name: ${n} images"
done
total=$(count_images "$OUT_ROOT")
log "  TOTAL: ${total} images"
log ""
log "다음 단계:"
log "  1. REFUGE 수동 배치 (미완 시)"
log "  2. GPU: python scripts/preprocess_all.py  # Glaucoma_extra2 → resized_cache"
log "  3. bash scripts/build_glaucoma_v3_manifest.sh"
log "  4. USE_GL_V3=1 bash scripts/build_v10_manifest.sh"
log "  5. V10E=1 bash scripts/start_v10_train.sh"
