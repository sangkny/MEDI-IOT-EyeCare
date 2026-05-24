# MEDI-IOT DR CNN — 원격 학습 가이드 (레거시 경로)

> **권장 SSOT**: [`../training/README.md`](../training/README.md) · `training/docker-compose.train.yml`  
> 이 디렉터리(`training-remote/`)는 동일 목적의 초기 compose 래퍼이며, 신규 작업은 **`training/`** 키트를 사용하세요.

**GPU 인프라 (2026-05-24)** — CNN 훈련은 **원격 `192.168.0.23` (TITAN X 12GB)** 에서만 실행. 개발 PC `192.168.0.12` (TITAN RTX 24GB)는 LM Studio·`docker-compose.dev.yml` LLM 전용.

API Docker 컨테이너(`medi-iot-api`, 메모리 2~4GB)에서는 **EfficientNet-B4 30 epoch** 학습이 OOM(exit 137)으로 중단되는 경우가 많습니다.  
**학습 전용 Docker 이미지(CPU / GPU)** 를 원격 서버에서 실행하고, 산출물 `.pt` / `.onnx` / `.meta.json` 만 개발 PC로 가져오는 방식을 권장합니다.

---

## 0. Docker로 학습 (권장)

| 변형 | 이미지 | 용도 |
|------|--------|------|
| **GPU** | `medi-dr-train:gpu` | B4·Messidor·30 epoch (CUDA 12.4) |
| **CPU** | `medi-dr-train:cpu` | 합성 검증·B0·GPU 없는 서버 |

### 사전 요구

- Docker 24+ / Compose v2
- **GPU**: [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) 설치 후 `nvidia-smi` 동작

### 빠른 시작 (프로젝트 루트 `MEDI-IOT-EyeCare`)

```bash
cd projects/MEDI-IOT-EyeCare

# GPU — 합성 1,000장 → 학습 → ONNX → eval (기본 CMD)
docker compose -f training-remote/docker-compose.gpu.yml build
docker compose -f training-remote/docker-compose.gpu.yml run --rm dr-train

# CUDA 동작 확인
docker compose -f training-remote/docker-compose.gpu.yml run --rm dr-train check

# CPU — 메모리 16GB 할당, B0 기본
docker compose -f training-remote/docker-compose.cpu.yml build
docker compose -f training-remote/docker-compose.cpu.yml run --rm dr-train
```

**Windows (PowerShell)**

```powershell
cd E:\Office_Automation\idea-collection\projects\MEDI-IOT-EyeCare
.\training-remote\docker-train.ps1 -Variant gpu -Action build
.\training-remote\docker-train.ps1 -Variant gpu -Action synthetic
.\training-remote\docker-train.ps1 -Variant gpu -Action check
```

**래퍼 스크립트 (Linux/macOS)**

```bash
chmod +x training-remote/docker-train.sh
./training-remote/docker-train.sh gpu build
./training-remote/docker-train.sh gpu synthetic
./training-remote/docker-train.sh cpu synthetic
```

### Messidor 실데이터 (Docker)

호스트에 `/data/messidor2` (또는 `D:\datasets\messidor2`) 를 두고, compose 가 프로젝트 루트 `..:/app` 로 마운트하므로 **컨테이너 안 경로**는 `/app` 기준입니다.

```bash
# 예: data 를 프로젝트 안에 둔 경우
# MEDI-IOT-EyeCare/data/messidor2/images/train/0/*.jpg ...

docker compose -f training-remote/docker-compose.gpu.yml run --rm dr-train \
  bash training-remote/run_messidor_pipeline.sh /app/data/messidor2
```

### 환경 변수 (선택)

`training-remote/env.train.example` → `.env` 로 복사 후 compose 와 같은 디렉터리에 두거나 export:

```bash
export ARCH=efficientnet_b4 BATCH=16 EPOCHS=30 OUT=models/retinal_messidor.pt
docker compose -f training-remote/docker-compose.gpu.yml run --rm dr-train \
  bash training-remote/run_messidor_pipeline.sh /app/data/messidor2
```

### Docker 파일 목록

| 파일 | 설명 |
|------|------|
| `Dockerfile.gpu` | PyTorch CUDA 12.4 runtime |
| `Dockerfile.cpu` | python:3.11-slim + PyTorch CPU |
| `docker-compose.gpu.yml` | `gpus: all`, B4·batch 16 기본 |
| `docker-compose.cpu.yml` | `mem_limit: 16g`, B0·batch 32 기본 |
| `docker-entrypoint.sh` | `check` 서브커맨드로 CUDA 점검 |
| `docker-train.sh` / `docker-train.ps1` | build / synthetic / messidor / shell |

산출물은 **볼륨 마운트** (`..:/app`) 덕분에 호스트의 `models/`, `data/`, `reports/` 에 그대로 남습니다.

---

## 1. 무엇을 학습하는가

| 항목 | 내용 |
|------|------|
| 태스크 | 당뇨망막병증(DR) **5등급** 분류 (ETDRS 0~4) |
| 기본 백본 | `efficientnet_b4` (운영 목표) |
| 전처리 | `clahe` (기본) — `services/retinal_cnn.py` 와 동일 |
| 입력 크기 | 224×224 RGB |
| 추론 연동 | `MEDI_CNN_MODEL_PATH` → ONNX, `meta.json` 의 `arch`·`preprocess`·`image_size` 일치 필수 |

**녹내장·AMD** 는 별도 헤드/데이터셋이 필요합니다. 현재 패키지는 **DR(Messidor/APTOS 계열)** 전용입니다.

---

## 2. 원격 서버에 복사할 파일

아래 디렉터리 전체를 압축해 GPU 서버에 풉니다.

```
MEDI-IOT-EyeCare/          # 학습 시 루트로 사용
├── services/
│   └── retinal_cnn.py     # 필수 (모델·전처리 SSOT)
├── scripts/
│   ├── generate_synthetic_fundus.py
│   ├── build_messidor2_manifest.py
│   ├── download_datasets.py
│   ├── train_retinal.py
│   ├── eval_messidor.py
│   └── export_onnx.py
├── training-remote/
│   ├── README.md          # 본 문서
│   ├── requirements-train.txt
│   ├── run_synthetic_pipeline.sh
│   ├── run_messidor_pipeline.sh
│   └── pack_for_remote.sh
└── requirements-ml.txt    # 또는 requirements-train.txt
```

**복사하지 않아도 되는 것**: `main.py`, `api/`, DB, Docker, `shared-libraries` (학습 스크립트는 `retinal_cnn` 만 import).

### Windows에서 압축 예 (PowerShell)

```powershell
cd E:\Office_Automation\idea-collection\projects\MEDI-IOT-EyeCare
.\training-remote\pack_for_remote.ps1
# → training-remote\medi-dr-train-bundle.zip 생성
```

### Linux/macOS

```bash
cd projects/MEDI-IOT-EyeCare
bash training-remote/pack_for_remote.sh
# → training-remote/medi-dr-train-bundle.tar.gz
```

---

## 3. 원격 서버 환경 준비

> **Docker 사용 시** 아래 Python venv 절차는 생략해도 됩니다. §0 Docker 절을 따르세요.

### 권장 사양

| 구분 | 최소 | 권장 (B4·30 epoch) |
|------|------|---------------------|
| RAM | 8 GB (B0·합성) | **16 GB+** |
| GPU | 없음 가능(CPU) | **8GB+ VRAM** (CUDA) |
| 디스크 | 5 GB | Messidor+APTOS 시 **20 GB+** |

### Python 환경

```bash
cd MEDI-IOT-EyeCare
python3 -m venv .venv-train
source .venv-train/bin/activate   # Windows: .venv-train\Scripts\activate

pip install -U pip
pip install -r training-remote/requirements-train.txt

# GPU (CUDA 12.x 예시)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
```

`requirements-train.txt` 는 **numpy&lt;2** 로 고정합니다 (onnxruntime 호환).

---

## 4. 데이터 준비

### A. 합성 데이터 (메모리·디스크 부담 적음, 파이프라인 검증)

```bash
bash training-remote/run_synthetic_pipeline.sh
```

- `data/synthetic/` — 1,000장 (등급당 200)
- `data/synthetic_manifest.json`

### B. Messidor-2 / APTOS (임상 목표 QWK≥0.85)

1. [Messidor-2](https://www.adcis.net/en/third-party/messidor2/) 등에서 이미지·라벨 다운로드 (라이선스 준수).
2. 디렉터리 예:

```
/data/messidor2/
  images/
    train/0/*.jpg … train/4/*.jpg
    val/…
    test/…
```

3. 매니페스트:

```bash
python scripts/build_messidor2_manifest.py \
  --data-dir /data/messidor2 \
  --output data/messidor2_manifest.json
```

Kaggle API가 있으면:

```bash
export KAGGLE_USERNAME=...
export KAGGLE_KEY=...
python scripts/download_datasets.py --dataset aptos2019
```

---

## 5. 학습 (핵심)

### EfficientNet-B4 + GPU (권장)

```bash
export PYTHONPATH="$(pwd)"

python scripts/train_retinal.py \
  --arch efficientnet_b4 \
  --manifest data/messidor2_manifest.json \
  --preprocess clahe \
  --epochs 30 \
  --batch-size 16 \
  --lr 0.0001 \
  --device cuda \
  --early-stop 5 \
  --skip-onnx \
  --output models/retinal_v2.pt
```

- **`--skip-onnx`**: 학습 직후 ONNX 변환 시 RAM 피크가 커서 OOM 나는 경우가 많음 → 학습·평가 후 `export_onnx.py` 로 분리.
- **`--early-stop 5`**: val QWK 5 epoch 무개선 시 중단.

### CPU만 있을 때 (메모리 절약)

```bash
python scripts/train_retinal.py \
  --arch efficientnet_b0 \
  --manifest data/synthetic_manifest.json \
  --epochs 30 \
  --batch-size 32 \
  --device cpu \
  --early-stop 3 \
  --skip-onnx \
  --output models/retinal_v2.pt
```

B0는 B4보다 가볍지만 **Messidor 벤치마크** 는 B4/MSEF-Net 이 유리합니다.

### OOM(exit 137) 대응 체크리스트

1. `--batch-size` 8 → 4 로 축소  
2. `--skip-onnx` 사용  
3. 다른 프로세스(Docker medi-iot-api) 중지  
4. `efficientnet_b0` 로 스모크 후 B4 재시도  
5. GPU 서버로 이전  

---

## 6. 평가

```bash
python scripts/export_onnx.py \
  --model models/retinal_v2.pt \
  --output models/retinal_v2.onnx

python scripts/eval_messidor.py \
  --model models/retinal_v2.onnx \
  --manifest data/messidor2_manifest.json \
  --split test \
  --output reports/
```

목표 (Messidor hold-out 참고):

| 지표 | 목표 |
|------|------|
| QWK | **≥ 0.85** |
| Referral sensitivity (grade≥2) | **≥ 0.85** |
| 단일 이미지 confidence | **> 0.50** (스모크 랜덤 가중치 ~0.20 대비) |

`reports/eval_test_YYYYMMDD.json` 에 수치가 기록됩니다.

---

## 7. 산출물을 본 프로젝트로 가져오기

원격에서 다음 **3개(+선택 pt)** 만 복사:

```
models/retinal_v2.pt          # ~16MB(B0) ~70MB(B4)
models/retinal_v2.onnx        # 추론 기본
models/retinal_v2.meta.json   # arch, preprocess, image_size, qwk
```

### scp 예

```bash
scp user@gpu-server:/path/MEDI-IOT-EyeCare/models/retinal_v2.* \
    ./projects/MEDI-IOT-EyeCare/models/
```

### Docker 개발 환경 반영

`projects/docker-compose.dev.yml` (이미 기본값):

```yaml
MEDI_INFERENCE_BACKEND: cnn
MEDI_CNN_MODEL_PATH: models/retinal_v2.onnx
MEDI_CNN_ARCH: efficientnet_b4   # meta.json arch 와 일치시킬 것
```

`meta.json` 이 `efficientnet_b0` 이면 `MEDI_CNN_ARCH=efficientnet_b0` 로 맞춥니다.

```bash
docker compose -f projects/docker-compose.dev.yml restart medi-iot-api
docker exec medi-iot-api-dev python3 /app/scripts/e2e_fundus_smoke.py
```

### MinIO 운영 업로드 (선택)

```bash
mc cp models/retinal_v2.onnx local/medi-dev/models/
mc cp models/retinal_v2.meta.json local/medi-dev/models/
```

---

## 8. 한 줄 파이프라인 (합성·검증용)

```bash
bash training-remote/run_synthetic_pipeline.sh
```

Messidor 실데이터:

```bash
bash training-remote/run_messidor_pipeline.sh /data/messidor2
```

---

## 9. 본 프로젝트 vs 원격 역할

| 위치 | 역할 |
|------|------|
| **원격 GPU 서버** | 데이터 다운로드, `train_retinal.py`, `eval_messidor.py`, ONNX export |
| **MEDI-IOT-EyeCare (Docker)** | `InferenceRouter`, Fundus Lab, 파트너 API, GradCAM — **추론만** |
| **Git** | 스크립트·문서만 커밋. `models/*.onnx`, `data/` 는 **제외** |

나중에 본机 메모리가 늘면 동일 `scripts/` 로 로컬 학습해도 됩니다. 원격과 동일한 매니페스트·환경변수만 맞추면 됩니다.
