# 훈련 전 진행 체크리스트 (retinal_v3 학습 24h+ 후)

> **훈련이 필요 없는 작업** — 기존 `retinal_v1`(스모크) / `retinal_v2`(합성) 로 검증 가능.

## A. 지금 (오늘) — ✅ 완료

| # | 작업 | 상태 |
|---|------|------|
| A1 | `.env.local` auto / PATH 비움 | ✅ |
| A2 | Compose 재기동 (`--force-recreate`) | ✅ |
| A3 | E2E 스모크 (`MEDI_SMOKE_IN_CONTAINER=1`) | ✅ |
| A3b | 호스트 curl `host_fundus_partner_smoke.ps1` | ✅ |
| A4 | 파트너 테이블 | ✅ |
| A5 | MinIO dry-run v3 | ✅ (업로드 전 — 객체 없음 정상) |
| A6 | 단위 테스트 8 passed | ✅ |
| A7 | Fundus Lab / Video DR | ✅ HTTP 200 |
| A8 | 파트너 analyze + GradCAM | ✅ |
| A8b | 파트너 FHIR `host_partner_fhir_smoke.ps1` | ✅ Bundle |
| A9 | API 이미지 numpy 1.26 + opencv + ort | ✅ |

## B. 훈련 24h 전 (데이터·인프라) — ✅ 준비 완료

| # | 작업 | 상태 |
|---|------|------|
| B1 | Messidor/APTOS 경로 | 📋 `data/README.md` (수동 다운로드 대기) |
| B2 | 합성 manifest | ✅ `data/synthetic_manifest.json` (1000장) |
| B3 | `data-prep` Docker | ✅ |
| B4 | `medi-train:gpu` 빌드 | ✅ |
| B5 | eval 파이프라인 검증 | ✅ v2 합성 test QWK 1.0 → `reports/eval_test_*.json` |

```bash
# 합성 데이터·manifest 재생성
docker compose -f training/docker-compose.train.yml run --rm data-prep

# eval (API 컨테이너)
docker exec medi-iot-api-dev python3 /app/scripts/eval_messidor.py \
  --model models/retinal_v2.onnx \
  --manifest data/synthetic_manifest.json --split test --output reports/
```

## C. 훈련 당일 (24h 후)

| # | 작업 |
|---|------|
| C1 | Messidor 배치 후 `train-gpu` → `retinal_v3.*` |
| C2 | `eval_messidor.py` — **QWK ≥ 0.85** (실데이터) |
| C3 | `deploy_model.py --target minio` |
| C4 | `AUTO_PULL` / `download_model.py` + API 재시작 |
| C5 | `host_fundus_partner_smoke.ps1` 회귀 |

```bash
docker compose -f training/docker-compose.train.yml run --rm train-gpu \
  python training/train.py \
  --manifest data/messidor2_manifest.json \
  --arch efficientnet_b4 --epochs 50 --output models/retinal_v3.pt
```

## 레거시

- `training-remote/` → **`training/`** SSOT
