# MEDI-IOT 학습 데이터 디렉터리

가중치·대용량 이미지는 **Git 제외**. 원격 GPU `192.168.0.23` 에 배치 후 학습한다.

## Messidor-2 (retinal_v4)

```
data/messidor2/images/
  train/0/ … train/4/
  val/0/   … val/4/
  test/0/  … test/4/
```

```bash
# manifest (원격 또는 개발 PC)
python training/download_data.py \
  --mode manifest \
  --data-dir data/messidor2 \
  --manifest-out data/messidor2_manifest.json
```

학습 SSOT: [`training/RETINAL_V4.md`](../training/RETINAL_V4.md)

## 합성 (retinal_v3 스모크)

```
data/synthetic/
data/synthetic_manifest.json
```

```bash
docker compose -f training/docker-compose.train.yml run --rm data-prep
```

## 전송 예시

```bash
# 로컬 → 원격
scp -r data/messidor2 root@192.168.0.23:~/MEDI-IOT-EyeCare/data/

# 원격 → 개발 PC (모델)
scp root@192.168.0.23:~/MEDI-IOT-EyeCare/models/retinal_v4.* models/
```
