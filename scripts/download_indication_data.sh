#!/bin/bash
# 추가 적응증 데이터셋 다운로드 가이드
# GPU 서버: ~/workspace/dataset/ 에 저장

set -euo pipefail

DATA_ROOT="${DATA_ROOT:-$HOME/workspace/dataset}"

echo "=== MEDI-IOT 다중 적응증 데이터셋 준비 ==="
echo "DATA_ROOT=$DATA_ROOT"
echo ""

# 1. REFUGE (Glaucoma) — grand-challenge.org
# 수동 다운로드 필요 (계정 필요)
# 1,200장: 훈련400 + 검증400 + 테스트400
# 라벨: glaucoma(1)/normal(0)
# URL: https://refuge.grand-challenge.org/
mkdir -p "$DATA_ROOT/REFUGE_raw"
echo "[1/5] REFUGE — https://refuge.grand-challenge.org/"
echo "      계정 생성 → 데이터 요청 → 승인 후 압축 해제 → $DATA_ROOT/REFUGE_raw"

# 2. AIROGS (Glaucoma) — grand-challenge.org
# 101,442장 (Rotterdam EyePACS)
# 라벨: RG/NRG (Referable Glaucoma)
# URL: https://airogs.grand-challenge.org/
mkdir -p "$DATA_ROOT/AIROGS_raw/images"
echo "[2/5] AIROGS — https://airogs.grand-challenge.org/"
echo "      train_labels.csv + images/ → $DATA_ROOT/AIROGS_raw"

# 3. ADAM (AMD) — IEEE DataPort
# 1,200장: AMD(400)/non-AMD(800)
# URL: https://ieee-dataport.org/ADAM
mkdir -p "$DATA_ROOT/ADAM_raw"
echo "[3/5] ADAM — https://ieee-dataport.org/ADAM"
echo "      AMD/ Non-AMD 폴더 → $DATA_ROOT/ADAM_raw"

# 4. iChallenge-AMD
# 400장: 정상/dry/wet AMD
mkdir -p "$DATA_ROOT/iChallengeAMD_raw"
echo "[4/5] iChallenge-AMD — https://amd.grand-challenge.org/"
echo "      → $DATA_ROOT/iChallengeAMD_raw"

# 5. ODIR-2019 (8개 질환) — Kaggle
# 10,000장: Normal/DR/Glaucoma/AMD/...
# kaggle competitions download -c ocular-disease-recognition-odir2019
mkdir -p "$DATA_ROOT/ODIR2019_raw/images"
echo "[5/5] ODIR-2019 — Kaggle ocular-disease-recognition-odir2019"
echo "      labels.csv + images/ → $DATA_ROOT/ODIR2019_raw"

echo ""
echo "디렉토리 생성 완료"
echo "각 데이터셋을 수동으로 다운로드 후:"
echo "  python training/make_manifest.py \\"
echo "    --data-root $DATA_ROOT \\"
echo "    --sources refuge,brazil,adam,odir \\"
echo "    --output training/manifests/multi_indication.json"
