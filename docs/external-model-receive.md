# 외부 GPU 훈련 결과 수령 · 배포 (SSOT)

외부 서버에서 `retinal_v3.{pt,onnx,meta.json}` 을 받은 뒤 **동일 절차**로 검증·배포합니다.

## 1. 외부 서버에서 가져오기

```bash
# 예: GPU 서버 → 개발 PC
scp user@gpu-host:/path/MEDI-IOT-EyeCare/models/retinal_v3.* \
  ./models/incoming/
```

필수: `retinal_v3.onnx`, `retinal_v3.meta.json`  
권장: `retinal_v3.pt` (GradCAM)

## 2. 수령 파이프라인 (한 번에)

```bash
cd projects/MEDI-IOT-EyeCare

python scripts/receive_external_model.py \
  --from-dir models/incoming \
  --stem retinal_v3

# MinIO 업로드까지
python scripts/receive_external_model.py \
  --from-dir models/incoming \
  --stem retinal_v3 \
  --upload-minio
```

이미 `models/` 에 있으면:

```bash
python scripts/verify_external_model.py --stem retinal_v3
```

## 3. 검증 항목 (`verify_external_model.py`)

| 검사 | 설명 |
|------|------|
| 파일 존재 | `.onnx` + `.meta.json` (+ `.pt`) |
| meta 필드 | `arch`, `preprocess`, `image_size`, `onnx` |
| onnxruntime | 랜덤 입력 추론 shape |
| resolver | `MEDI_CNN_MODEL_PATH` 호환 |

## 4. MinIO → API

```bash
python training/deploy_model.py --model retinal_v3.onnx --target minio
python scripts/download_model.py --model retinal_v3.onnx --dry-run
cd ../.. && docker compose -f docker-compose.dev.yml up -d medi-iot-api --force-recreate
```

`MEDI_CNN_MODEL_VERSION=auto` 이면 **v3 로컬/MinIO 우선** 선택.

## 5. 임상 지표 (실데이터)

```bash
docker exec medi-iot-api-dev python3 /app/scripts/eval_messidor.py \
  --model models/retinal_v3.onnx \
  --manifest data/messidor2_manifest.json \
  --split test --output reports/
```

**배포 기준**: Messidor test **QWK ≥ 0.85** (합성 1.0 은 파이프라인 검증용만).

## 6. API 회귀

```powershell
scripts\host_fundus_partner_smoke.ps1
scripts\host_partner_fhir_smoke.ps1
```

## 7. Dry-run (훈련 전 연습)

1 epoch GPU 합성 학습으로 번들 생성 (실제 v3 대체용):

```bash
docker compose -f training/docker-compose.train.yml run --rm --entrypoint python train-gpu \
  training/train.py --manifest data/synthetic_manifest.json \
  --arch efficientnet_b0 --epochs 1 --output models/retinal_v3.pt --device cuda
```

> 실제 Messidor 학습 후에는 위 파일을 **덮어쓰기**하고 2~6절만 반복.
