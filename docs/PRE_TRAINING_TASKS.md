# 훈련 전 진행 체크리스트 (retinal_v3 학습 24h+ 후)

> **훈련이 필요 없는 작업** — 기존 `retinal_v1`(스모크) / `retinal_v2`(합성) 로 검증 가능.

## A. 지금 (오늘)

| # | 작업 | 명령 / 경로 |
|---|------|-------------|
| A1 | `.env.local` v1 고정 해제 | `MEDI_CNN_MODEL_VERSION=auto`, `MEDI_CNN_MODEL_PATH=` (비움) |
| A2 | Compose 재기동 + sync 로그 | `cd projects && docker compose -f docker-compose.dev.yml restart medi-iot-api` |
| A3 | E2E 스모크 | `docker exec -e MEDI_SMOKE_IN_CONTAINER=1 medi-iot-api-dev python3 /app/scripts/e2e_fundus_smoke.py` |
| A3b | 호스트 curl | `scripts/host_fundus_partner_smoke.ps1` (Fundus Lab + 파트너) |
| A4 | 파트너 테이블 | `docker exec medi-iot-api-dev python3 /app/scripts/ensure_partner_tables.py` |
| A5 | MinIO 경로 dry-run | `python3 scripts/download_model.py --model retinal_v3.onnx --dry-run` |
| A6 | 단위 테스트 | `pytest tests/test_cnn_model_resolver.py tests/test_inference_router.py -q` |
| A7 | Fundus Lab / Video DR | e2e 스모크 Step 3·7 또는 브라우저 `:8001` |
| A8 | SaMD 파트너 API | e2e `partner/register` + `partner/analyze` (GradCAM) |
| A9 | API 이미지 재빌드 | `requirements.txt` opencv+onnxruntime 추가 후 `docker compose build medi-iot-api` |

**주의**: `.env.local` 변경 후 `restart`만으로 env 미반영 → `up -d medi-iot-api --force-recreate` 필요.

## B. 훈련 24h 전 (데이터만)

| # | 작업 | 비고 |
|---|------|------|
| B1 | Messidor/APTOS 라이선스·경로 확보 | Git 제외 `data/` |
| B2 | manifest 생성 | `scripts/build_messidor2_manifest.py` |
| B3 | `training/download_data.py` | `--mode manifest` / synthetic 검증 |
| B4 | GPU 서버 Docker | `training/docker-compose.train.yml build train-gpu` |

## C. 훈련 당일 (24h 후)

| # | 작업 |
|---|------|
| C1 | `train-gpu` 실데이터 학습 → `retinal_v3.*` |
| C2 | `eval_messidor.py` — QWK ≥ 0.85 |
| C3 | `deploy_model.py --target minio` |
| C4 | `download_model.py` 또는 `AUTO_PULL` + API 재시작 |
| C5 | 파트너 `/analyze` 회귀 + `meta.json` 버전 고정 |

## 레거시

- `training-remote/` → **`training/`** SSOT (`training/README.md`)
