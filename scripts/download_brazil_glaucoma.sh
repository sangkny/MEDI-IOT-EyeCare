#!/bin/bash
# Brazil Glaucoma Dataset (약 2,000장, 공개)
# https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9778370/

set -euo pipefail

DATA_ROOT="${DATA_ROOT:-$HOME/workspace/dataset/BrazilGlaucoma_raw}"
mkdir -p "$DATA_ROOT/normal" "$DATA_ROOT/glaucoma"

echo "=== Phase 1 Glaucoma 데이터 준비 ==="
echo ""
echo "Brazil Glaucoma 다운로드:"
echo "  1. https://data.mendeley.com/datasets/hwbjxfdnp6/1"
echo "  2. 또는 논문 연락처 통해 요청"
echo "  3. normal/ glaucoma/ 하위로 정리 → $DATA_ROOT"
echo ""
echo "REFUGE 다운로드 (권장, 1,200장):"
echo "  1. https://refuge.grand-challenge.org/"
echo "  2. 계정 생성 → 데이터 요청 → 승인 후 다운로드"
echo "  3. ~/workspace/dataset/REFUGE_raw/ 에 압축 해제"
echo ""
echo "manifest 생성:"
echo "  python training/make_manifest.py \\"
echo "    --data-root ~/workspace/dataset \\"
echo "    --sources refuge,brazil \\"
echo "    --output training/manifests/glaucoma_phase1.json"
echo ""
echo "Phase 1 학습 (이진→3등급 확장 전):"
echo "  python training/train_multitask.py \\"
echo "    --manifest training/manifests/glaucoma_phase1.json \\"
echo "    --tasks glaucoma \\"
echo "    --backbone efficientnet_b4 \\"
echo "    --output models/glaucoma_v1.pt"
