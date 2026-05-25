# 안저 DR 훈련 데이터셋 가이드

가중치·대용량 이미지는 **Git 제외**. GPU 서버 `192.168.0.23` 에 원본을 두고 manifest·학습을 수행한다.

## 데이터셋 현황 (2026-05-25)

| 데이터셋 | 이미지 수 | 라벨 | 위치 (GPU 서버) | 상태 |
|---------|---------|------|-----------------|------|
| APTOS 2019 | 3,662장 | 0~4 | `data/aptos2019_raw/` | ✅ 완료 |
| Messidor-2 | 1,057장 | 0~3→0~4 | `data/Messidor-2_raw/` | ✅ 완료 |
| IDRiD | 516장 | 0~4 | `data/IDRiD_raw/` | ✅ 완료 |
| DRIVE | 40장 | 혈관 세그멘테이션 | `data/DRIVE_raw/` | ✅ 완료 |
| EyePACS | 35,126장 | 0~4 | `/workspace/dataset/EyePACS_raw/` | ⏳ 해제 중 |

**통합 학습 (v4)**: APTOS + Messidor-2 + IDRiD = **5,235장** → `unified_manifest_v2.json` · val QWK **0.8204**

---

## GPU 서버 경로 (`192.168.0.23`, `smartvisionglobal`)

```
/home/smartvisionglobal/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare/
├── data/
│   ├── aptos2019_raw/
│   │   ├── train_images/      # 3,662장 PNG
│   │   └── train.csv          # id_code, diagnosis (0~4)
│   ├── Messidor-2_raw/
│   │   ├── IMAGES/            # 1,058장 PNG
│   │   └── messidor_data.csv  # image_id, adjudicated_dr_grade (0~3)
│   ├── IDRiD_raw/
│   │   └── B. Disease Grading/
│   │       ├── 1. Original Images/
│   │       │   ├── a. Training Set/   # 413장
│   │       │   └── b. Testing Set/    # 103장
│   │       └── 2. Groundtruths/
│   │           ├── a. IDRiD_Disease Grading_Training Labels.csv
│   │           └── b. IDRiD_Disease Grading_Testing Labels.csv
│   ├── DRIVE_raw/
│   │   ├── training/
│   │   └── test/
│   ├── unified_manifest_v2.json      # v4 학습용
│   └── unified_manifest_eyepacs.json # v5 예정
├── models/
│   ├── retinal_v3.{onnx,pt,meta.json}  # QWK=0.9975 (합성)
│   └── retinal_v4.{onnx,pt,meta.json}  # QWK=0.8204 (실데이터)
└── training/

/home/smartvisionglobal/workspace/dataset/
└── EyePACS_raw/
    ├── trainLabels.csv    # image, level (0~4)
    ├── train/             # 35,126장 JPEG (해제 중)
    └── test/              # 53,576장
```

개발 PC 반영:

```bash
scp smartvisionglobal@192.168.0.23:~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare/models/retinal_v4.{onnx,meta.json} models/
```

---

## 라벨 등급 통일 (ETDRS 0~4)

| 데이터셋 | 원본 등급 | 변환 | No DR | Mild | Moderate | Severe | PDR |
|---------|---------|------|-------|------|----------|--------|-----|
| APTOS | 0~4 | 없음 | 0 | 1 | 2 | 3 | 4 |
| Messidor-2 | 0~3 | **3→4** | 0 | 1 | 2 | — | 4 |
| IDRiD | 0~4 | 없음 | 0 | 1 | 2 | 3 | 4 |
| EyePACS | 0~4 | 없음 | 0 | 1 | 2 | 3 | 4 |

---

## 훈련 명령어

### retinal_v4 (현재 운영, 5,235장)

```bash
# 원격 GPU 서버
docker compose -f training/docker-compose.train.yml run --rm train-gpu \
  python training/train.py \
    --manifest data/unified_manifest_v2.json \
    --arch efficientnet_b4 \
    --preprocess clahe \
    --epochs 50 --batch-size 16 \
    --device cuda --early-stop 10 \
    --output models/retinal_v4.pt
```

### retinal_v5 (EyePACS 포함, ≥0.85 목표)

```bash
# EyePACS 해제 완료 확인
find /workspace/dataset/EyePACS_raw/train -name "*.jpeg" | wc -l
# 기대: 35126

# manifest 재생성 (서버 스크립트)
python3 /tmp/make_manifest_v2.py   # → unified_manifest_eyepacs.json

docker compose -f training/docker-compose.train.yml run --rm train-gpu \
  python training/train.py \
    --manifest data/unified_manifest_eyepacs.json \
    --arch efficientnet_b4 \
    --preprocess clahe \
    --epochs 50 --batch-size 16 \
    --device cuda --early-stop 10 \
    --output models/retinal_v5.pt
```

SSOT: [`training/RETINAL_V4.md`](../training/RETINAL_V4.md) · [`book/part7/ch32-retinal-dataset-training.md`](../../book/part7/ch32-retinal-dataset-training.md)
