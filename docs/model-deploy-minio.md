# retinal_v3 — MinIO 모델 배포 경로 (SSOT)

> **버킷·prefix·파일명** 은 아래 표만 따른다. `scripts/download_model.py` · `training/deploy_model.py` 기본값과 동일.

## S3 객체 레이아웃

| 항목 | 값 |
|------|-----|
| 버킷 | `medi-dev` |
| prefix | `models/` |
| ONNX | `s3://medi-dev/models/retinal_v3.onnx` |
| 메타 | `s3://medi-dev/models/retinal_v3.meta.json` |
| PyTorch (선택) | `s3://medi-dev/models/retinal_v3.pt` |
| URL 별칭 | `minio://medi-dev/models/` (`download_model.py --source`) |

Compose `minio-init` 가 버킷 `medi-dev` 만 생성한다. `models/` prefix 는 **첫 업로드 시 자동** 생성된다.

## 엔드포인트 (호스트 vs 컨테이너)

| 실행 위치 | `MEDI_AWS_ENDPOINT_URL` |
|-----------|-------------------------|
| Windows / WSL 호스트 (`download_model.py`) | `http://127.0.0.1:9000` |
| `medi-iot-api-dev` 컨테이너 | `http://minio:9000` (compose 기본) |

인증: `minioadmin` / `minioadmin` (`MEDI_AWS_ACCESS_KEY_ID` / `MEDI_AWS_SECRET_ACCESS_KEY`)

## 1. 업로드 (훈련 서버 → MinIO)

훈련 산출물이 `MEDI-IOT-EyeCare/models/` 에 있을 때:

```bash
cd projects/MEDI-IOT-EyeCare

# boto3 (호스트, MinIO :9000 노출)
python training/deploy_model.py --model retinal_v3.onnx --target minio

# 또는 mc (호스트)
docker run --rm --network host minio/mc:latest \
  mc alias set local http://127.0.0.1:9000 minioadmin minioadmin
docker run --rm -v "$(pwd)/models:/data" --network host minio/mc:latest \
  mc cp /data/retinal_v3.onnx local/medi-dev/models/
docker run --rm -v "$(pwd)/models:/data" --network host minio/mc:latest \
  mc cp /data/retinal_v3.meta.json local/medi-dev/models/
```

## 2. 다운로드 (MinIO → 개발 PC `models/`)

```bash
cd projects/MEDI-IOT-EyeCare

python scripts/download_model.py --model retinal_v3.onnx \
  --source minio://medi-dev/models/

# 경로만 점검 (다운로드 없음)
python scripts/download_model.py --model retinal_v3.onnx --dry-run
```

## 3. API 추론 연동 (자동 선택)

`projects/.env.local` — **권장** (명시 경로 없이 버전만 지정):

```env
MEDI_INFERENCE_BACKEND=cnn
MEDI_CNN_MODEL_VERSION=auto    # v3 → v2 → v1 로컬 우선
MEDI_CNN_AUTO_PULL=1           # 없으면 MinIO에서 기동 시 pull
MEDI_CNN_MODEL_PATH=           # 비우기 — VERSION/auto 해석
```

고정 버전만 쓸 때: `MEDI_CNN_MODEL_VERSION=v3` (또는 `v2`).

`meta.json` 의 `arch` 는 resolver 가 meta 에서 읽어 `MEDI_CNN_ARCH` 보다 우선(있을 때).

`download_model.py` 가 `.env.local` 에 `VERSION`·`AUTO_PULL`·`PATH` 를 함께 갱신한다.

```bash
cd projects
docker compose -f docker-compose.dev.yml restart medi-iot-api
docker exec medi-iot-api-dev python3 /app/scripts/e2e_fundus_smoke.py
```

## 4. 버전 매트릭스

| 파일 | 데이터 | MinIO 키 | 용도 |
|------|--------|----------|------|
| `retinal_v1.onnx` | 스모크 랜덤 | (선택) | 파이프라인 검증 |
| `retinal_v2.onnx` | 합성 B0 | `models/retinal_v2.*` | 현재 dev 기본 (compose) |
| `retinal_v3.onnx` | APTOS/Messidor | `models/retinal_v3.*` | **실데이터 배포 목표** |

## 5. 점검 체크리스트

```bash
python scripts/download_model.py --model retinal_v3.onnx --dry-run
docker run --rm --network mediiot-dev-network --entrypoint /bin/sh minio/mc:latest \
  -c "mc alias set local http://minio:9000 minioadmin minioadmin && mc ls local/medi-dev/models/"
```

- [ ] `retinal_v3.onnx` + `retinal_v3.meta.json` 이 `medi-dev/models/` 에 존재
- [ ] `onnxruntime` 검증 통과 (`download_model.py` 기본)
- [ ] `MEDI_CNN_MODEL_PATH` / `MEDI_CNN_ARCH` 갱신
- [ ] `medi-iot-api-dev` 재시작 후 E2E 스모크
