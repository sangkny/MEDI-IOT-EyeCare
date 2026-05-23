# 훈련 데이터 디렉터리 (Git 제외)

## 합성 (즉시 — 파이프라인 검증)

```bash
docker compose -f training/docker-compose.train.yml run --rm data-prep
# → data/synthetic/ + data/synthetic_manifest.json
```

## Messidor-2 (실데이터 — 24h 후 훈련)

1. [ADCIS Messidor-2](https://www.adcis.net/en/third-party/messidor2/) 에서 다운로드 (라이선스 동의)
2. 아래 구조로 배치:

```
data/messidor2/images/
  train/0/ ... train/4/
  val/0/   ... val/4/
  test/0/  ... test/4/
```

3. manifest:

```bash
python scripts/build_messidor2_manifest.py \
  --data-dir data/messidor2 \
  --output data/messidor2_manifest.json
```

4. GPU 학습:

```bash
docker compose -f training/docker-compose.train.yml run --rm train-gpu \
  python training/train.py \
  --manifest data/messidor2_manifest.json \
  --arch efficientnet_b4 --epochs 50 --output models/retinal_v3.pt
```

## APTOS 2019 (선택)

```bash
python scripts/download_datasets.py --dataset aptos2019 --processed-dir data
```

Kaggle API 필요 (`~/.kaggle/kaggle.json`). 실패 시 `--force-synthetic` 로 합성 fallback.
