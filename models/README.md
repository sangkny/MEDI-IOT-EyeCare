# 모델 파일 관리 가이드

> **중요**: `models/*.onnx`, `models/*.pt` 등 가중치 파일은 **Git에 포함하지 않습니다**.
> `git add` 시 **절대 `git add -A` 사용 금지** — 변경한 소스 파일만 파일명을 명시해 추가하세요.

## 저장 위치

| 환경 | 경로 |
|------|------|
| 개발 | `./models/` (로컬 전용, git 제외) |
| MinIO (SSOT) | `s3://medi-dev/models/` — 상세 [`docs/model-deploy-minio.md`](../docs/model-deploy-minio.md) |

### 버전별 MinIO 키

| 버전 | 객체 키 | 비고 |
|------|---------|------|
| v1 | `models/retinal_v1.onnx` | 스모크 |
| v2 | `models/retinal_v2.onnx` | 합성 B0 (현재 compose 기본) |
| **v3** | `models/retinal_v3.onnx` | **실데이터 배포 목표** (+ `.meta.json`) |

## MinIO 다운로드 (권장)

```bash
# 경로 점검 (업로드 전/후)
python scripts/download_model.py --model retinal_v3.onnx --dry-run

# 다운로드 + onnxruntime 검증 + projects/.env.local 갱신
python scripts/download_model.py --model retinal_v3.onnx \
  --source minio://medi-dev/models/
```

`mc` 사용 시:

```bash
mc alias set local http://127.0.0.1:9000 minioadmin minioadmin
mc cp local/medi-dev/models/retinal_v3.onnx ./models/
mc cp local/medi-dev/models/retinal_v3.meta.json ./models/
```

## MinIO 업로드 (훈련 후)

```bash
python training/deploy_model.py --model retinal_v3.onnx --target minio
```

## 원격 GPU 학습 (OOM 시)

`training/` 키트가 SSOT. 레거시: [`training-remote/README.md`](../training-remote/README.md).

- Compose: `training/docker-compose.train.yml`
- 가이드: [`training/README.md`](../training/README.md)

## 모델 직접 학습 (동일 머신)

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
