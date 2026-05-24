# retinal_v4 — Messidor/APTOS 실데이터 학습 가이드

**목적**: 합성 `retinal_v3`(파이프라인 검증)를 넘어 **임상 벤치마크**에서 일반화된 DR 분류 모델을 만든다.

| 구분 | retinal_v3 | **retinal_v4 (목표)** |
|------|------------|------------------------|
| 데이터 | 합성 1,000장 | **Messidor-2 / APTOS** (~1.7k~3.6k) |
| 학습 GPU | TITAN X @ `192.168.0.23` | 동일 |
| val QWK | ~1.0 (과적합 위험) | **test QWK ≥ 0.85** |
| 운영 confidence | ~0.675 (합성) | 실이미지에서 **안정적 calibration** |

---

## 1. 학습 목적 (Why)

1. **임상 신뢰**: Messidor-2는 DR 5등급 벤치 SSOT. 합성 QWK 0.99는 배포 근거가 되지 않음.
2. **파트너/SaMD**: `eval_messidor.py` 리포트 + `meta.json` 버전 고정 → 식약처 성능 평가 입력.
3. **운영 추론**: 학습 전처리(`clahe`)·`arch`·`image_size`가 `services/retinal_cnn.py`·ONNX와 **동일**해야 Fundus Lab·Partner API와 일치.

---

## 2. 실행 위치 (Where)

| 작업 | 호스트 |
|------|--------|
| LLM (4-agent, 설명) | 개발 PC `192.168.0.12` TITAN RTX · `docker-compose.dev.yml` |
| **CNN 훈련** | 원격 `192.168.0.23` TITAN X · `training/docker-compose.train.yml` |
| CNN 추론 | `medi-iot-api-dev` ONNX (CPU) |

```bash
# 원격 GPU 서버에서만
ssh root@192.168.0.23
cd ~/MEDI-IOT-EyeCare
bash training/run_retinal_v4_messidor.sh
```

---

## 3. 데이터 배치

```
data/messidor2/images/
  train/0/*.jpg … train/4/*.jpg
  val/0/ … val/4/
  test/0/ … test/4/
```

다운로드: [Messidor-2](https://www.adcis.net/en/third-party/messidor2/) (라이선스 준수).

```bash
docker compose -f training/docker-compose.train.yml run --rm data-prep \
  python training/download_data.py \
    --mode manifest \
    --data-dir data/messidor2 \
    --manifest-out data/messidor2_manifest.json
```

---

## 4. 하이퍼파라미터 의미

| 파라미터 | 권장값 (TITAN X 12GB) | 의미 |
|----------|----------------------|------|
| `--arch efficientnet_b4` | 고정 | Messidor 벤치에서 B0 대비 표현력·QWK 유리. v3 합성과 동일 백본. |
| `--preprocess clahe` | 고정 | 운영 `retinal_cnn.preprocess_fundus_array` 와 동일. 변경 시 ONNX·API 불일치. |
| `--epochs 50` | 30~50 | Cosine 스케줄 전체 구간. 데이터 적으면 30+early-stop. |
| `--batch-size 16` | 16→8 (OOM 시) | VRAM 피크. 12GB에서 B4·AMP 기준 16이 일반적. |
| `--lr 1e-4` | 1e-4 | AdamW + pretrained B4 fine-tune 표준. |
| `--early-stop 5` | 5 | **val QWK** 5 epoch 무개선 시 중단 — 과적합 방지. |
| `--device cuda` | cuda | 원격 GPU 필수. |
| (기본) AMP | 켜짐 | mixed precision — 속도·VRAM 절약. |
| WeightedRandomSampler | 자동 | 등급 불균형(0~4) 보정 — 소수 등급 recall 개선. |
| class-weight loss | 자동 | CrossEntropy 가중 — referral 민감도에 유리. |
| Early-stop metric | **val QWK** | accuracy보다 등급 순서(ordinal) 반영 — 임상 벤치 SSOT. |

환경 변수 (compose):

```bash
export ARCH=efficientnet_b4 EPOCHS=50 BATCH=16
docker compose -f training/docker-compose.train.yml run --rm train-gpu \
  python training/train.py \
    --manifest data/messidor2_manifest.json \
    --arch efficientnet_b4 \
    --preprocess clahe \
    --epochs 50 \
    --batch-size 16 \
    --lr 0.0001 \
    --early-stop 5 \
    --device cuda \
    --output models/retinal_v4.pt
```

---

## 5. 목표 성과 (Success criteria)

`scripts/eval_messidor.py` **test split**:

| 지표 | 목표 | 의미 |
|------|------|------|
| **QWK** | **≥ 0.85** | 등급 순서를 반영한 일치도 — Messidor 논문·SaMD 벤치 |
| Referral sensitivity (grade≥2) | ≥ 0.85 | 중등도 이상 referral 놓침 최소화 |
| AUC (참고) | > 0.93 | 문헌·ch27 목표 |
| 단일 이미지 confidence | > 0.50 | v2 랜덤 가중치(~0.20) 대비 운영 가독성 |

산출물:

- `models/retinal_v4.{pt,onnx,meta.json}`
- `reports/eval_test_*.json`

---

## 6. 개발 PC 반영

```bash
scp root@192.168.0.23:~/MEDI-IOT-EyeCare/models/retinal_v4.* models/
# projects/.env.local
# MEDI_CNN_MODEL_PATH=models/retinal_v4.onnx
# MEDI_CNN_MODEL_VERSION=v4
docker compose -f projects/docker-compose.dev.yml up -d medi-iot-api
docker exec medi-iot-api-dev python3 /app/scripts/e2e_fundus_smoke.py
docker exec medi-iot-api-dev python3 /app/scripts/eval_messidor.py \
  --model models/retinal_v4.onnx \
  --manifest data/messidor2_manifest.json \
  --split test --output reports/
```

MinIO: `python training/deploy_model.py --model retinal_v4.onnx --target minio`

---

## 7. v3 → v4 차이 요약

- v3: **파이프라인·GPU·compose 검증** (합성, QWK 과대)
- v4: **임상 배포 후보** (실데이터, QWK≥0.85 게이트)

`meta.json` 의 `trained_on`, `qwk` 를 Partner 환경에 고정 배포한다.
