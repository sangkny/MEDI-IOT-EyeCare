# MEDI-IOT DR Training Kit

**SSOT** for offline / remote GPU training. Inference stays in `medi-iot-api` (Docker dev compose).

Legacy alias: `training-remote/` (same workflows; prefer this directory).

## Structure

```
training/
├── Dockerfile.gpu          # nvidia/cuda:12.4.1 + torch 2.6 cu124
├── Dockerfile.cpu          # python:3.11-slim + torch CPU
├── docker-compose.train.yml
├── train.py                # AMP · WeightedRandomSampler · ONNX · meta.json
├── download_data.py
├── deploy_model.py         # MinIO / deploy checklist
├── run_training.sh
└── requirements.txt
```

## Quick start

From `MEDI-IOT-EyeCare/`:

```bash
# GPU — synthetic pipeline
docker compose -f training/docker-compose.train.yml build train-gpu
docker compose -f training/docker-compose.train.yml run --rm data-prep
docker compose -f training/docker-compose.train.yml run --rm train-gpu

# Or one script (Linux)
bash training/run_training.sh gpu
```

```powershell
# Windows
docker compose -f training/docker-compose.train.yml build train-gpu
docker compose -f training/docker-compose.train.yml run --rm data-prep
docker compose -f training/docker-compose.train.yml run --rm train-gpu
```

## Eval (훈련 전·후)

```bash
# API 컨테이너 (권장)
docker exec medi-iot-api-dev python3 /app/scripts/eval_messidor.py \
  --model models/retinal_v2.onnx \
  --manifest data/synthetic_manifest.json \
  --split test --output reports/
```

## Real data (Messidor / APTOS)

1. Place images under `data/messidor2/images/{train,val,test}/{0..4}/`
2. `python training/download_data.py --mode manifest --data-dir data/messidor2 --manifest-out data/messidor2_manifest.json`
3. Train:

```bash
docker compose -f training/docker-compose.train.yml run --rm train-gpu \
  python training/train.py \
    --manifest data/messidor2_manifest.json \
    --arch efficientnet_b4 \
    --epochs 50 \
    --output models/retinal_v3.pt
```

## Deploy to API host (MinIO → medi-iot-api)

**SSOT**: [`docs/model-deploy-minio.md`](../docs/model-deploy-minio.md)

| 단계 | 명령 |
|------|------|
| 경로 점검 | `python scripts/download_model.py --model retinal_v3.onnx --dry-run` |
| 업로드 | `python training/deploy_model.py --model retinal_v3.onnx --target minio` |
| 다운로드 | `python scripts/download_model.py --model retinal_v3.onnx` |
| API 재시작 | `cd ../.. && docker compose -f docker-compose.dev.yml restart medi-iot-api` |

MinIO 키: `s3://medi-dev/models/retinal_v3.{onnx,meta.json}` · 호스트 endpoint `http://127.0.0.1:9000`

Book: `book/part7/ch27-medi-r4-ml.md` §27.6 · `book/part7/ch30-samd-partner-platform.md` §30.7
