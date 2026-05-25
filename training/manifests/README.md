# Manifest 파일 (training SSOT)

대용량 manifest는 **Git 제외** (`.gitignore`). GPU 서버에서 `make_manifest.py` 로 생성한다.

## 파일

| 파일 | 데이터셋 | 장수(대략) | Git |
|------|---------|-----------|-----|
| `sample_synthetic.json` | synthetic | 25 | ✅ 포함 |
| `unified_v4.json` | APTOS+Messidor+IDRiD | 5,235 | ❌ 로컬 생성 |
| `unified_eyepacs.json` | +EyePACS | ~40k | ❌ 로컬 생성 |

## 생성 (SSOT: `training/make_manifest.py`)

```bash
cd MEDI-IOT-EyeCare

# 파이프라인 테스트 (등급당 5장)
python training/make_manifest.py \
  --datasets synthetic \
  --sample 5 \
  --output training/manifests/sample_synthetic.json

# v4 (EyePACS 제외)
python training/make_manifest.py \
  --datasets aptos messidor2 idrid \
  --output training/manifests/unified_v4.json

# v5 (EyePACS 포함, GPU 서버)
python training/make_manifest.py \
  --datasets aptos messidor2 idrid eyepacs \
  --output training/manifests/unified_eyepacs.json \
  --eyepacs-dir /home/smartvisionglobal/workspace/dataset/EyePACS_raw
```

## 학습 연동

```bash
docker compose -f training/docker-compose.train.yml run --rm train-gpu \
  python training/train.py \
    --manifest training/manifests/unified_v4.json \
    --output models/retinal_v4.pt
```

`data_dir`·`path` 는 `train.py` / `FundusManifestDataset` 과 동일 규칙 (`data/` 기준 상대경로).

## Git 동기화

1. 개발 PC: `make_manifest.py` + `manifests/README.md` + `sample_*.json` **push**
2. GPU 서버: `git pull` → `make_manifest.py` 로 `unified_*.json` **생성** (커밋 안 함)
3. 학습 후: `models/*.meta.json` 만 **push** → 개발 PC `pull` + `scp` onnx
