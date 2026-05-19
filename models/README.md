# 모델 파일 관리 가이드

> **중요**: `models/*.onnx`, `models/*.pt` 등 가중치 파일은 **Git에 포함하지 않습니다**.
> `git add` 시 **절대 `git add -A` 사용 금지** — 변경한 소스 파일만 파일명을 명시해 추가하세요.

## 저장 위치

| 환경 | 경로 |
|------|------|
| 개발 | `./models/` (로컬 전용, git 제외) |
| 운영 | S3/MinIO `medi-dev` 버킷 `models/` prefix |

## 모델 다운로드 (MinIO)

```bash
mc alias set local http://localhost:9000 minioadmin minioadmin
mc cp local/medi-dev/models/retinal_v1.onnx ./models/
mc cp local/medi-dev/models/retinal_v1.pt   ./models/
mc cp local/medi-dev/models/retinal_v1.meta.json ./models/
```

## 모델 직접 학습

```bash
pip install -r requirements-ml.txt

# Messidor manifest (D1)
python scripts/build_messidor2_manifest.py \
  --data-dir /data/messidor2 \
  --output datasets/messidor2/manifest.json

# EfficientNet-B4 (기본) + CLAHE 전처리
python scripts/train_retinal.py \
  --arch efficientnet_b4 \
  --preprocess clahe \
  --manifest datasets/messidor2/manifest.json \
  --epochs 30 \
  --output-dir models

# MSEF-Net (B0+B4 멀티스케일 융합)
python scripts/train_retinal.py \
  --arch msef_net \
  --preprocess both \
  --manifest datasets/messidor2/manifest.json \
  --epochs 30 \
  --output-dir models
```

산출물: `models/retinal_v1.pt`, `models/retinal_v1.onnx`, `models/retinal_v1.meta.json`

## Hold-out 평가

```bash
python scripts/eval_messidor.py \
  --model models/retinal_v1.onnx \
  --manifest datasets/messidor2/manifest.json \
  --split val \
  --output reports/
```

## 데이터셋 링크

| 데이터셋 | URL |
|----------|-----|
| Messidor-2 | https://www.adcis.net/en/third-party/messidor2/ |
| APTOS 2019 | https://kaggle.com/competitions/aptos2019-blindness-detection |
| EyePACS | https://kaggle.com/competitions/diabetic-retinopathy-detection |
| IDRiD | https://ieee-dataport.org/open-access/indian-diabetic-retinopathy-image-dataset-idrid |

## RETFound (선택)

`MEDI_USE_FOUNDATION_MODEL=retfound` — `services/retinal_foundation.py` 참고.
로컬 체크포인트 없으면 **경고만** 출력하고 EfficientNet 경로로 진행합니다.
