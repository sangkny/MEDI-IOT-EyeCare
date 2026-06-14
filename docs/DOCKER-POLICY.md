# Docker 운영 정책 — MEDI-IOT-EyeCare

> 최종 업데이트: 2026-06-12  
> SSOT: `projects/docker-compose.dev.yml` (개발 PC) · `scripts/start_v10_train.sh` (GPU)  
> 레지스트리: `docs/DOCKER-REGISTRY.md`

---

## 실행 환경 원칙 (필수)

> **Python은 호스트(WSL/GPU Ubuntu)에서 직접 실행 금지** — 환경·CUDA·패키지 불일치 방지.

### 개발 PC (Windows + WSL2 + Docker Desktop)

| 작업 | 실행 방법 |
|------|-----------|
| pytest / 스크립트 | `docker exec medi-iot-api-dev python3 ...` |
| compose 서비스 | `docker compose -f projects/docker-compose.dev.yml exec ...` |
| **금지** | WSL에서 `python3` 직접 실행 |

```powershell
docker exec medi-iot-api-dev python -m pytest tests/test_fundus_enhancement.py -v
docker exec medi-iot-api-dev python3 scripts/compare_enhancement.py --image /app/fundus_right_sklee.jpg
```

### GPU 서버 (Ubuntu 18.04 + Docker)

| 작업 | 실행 방법 |
|------|-----------|
| 훈련 | `docker run --gpus all --rm medi-train:gpu ...` (`start_v10_train.sh`) |
| 전처리 | `docker run --rm medi-train:gpu ...` |
| Kaggle 다운로드 | `bash scripts/run_kaggle_gl_download_gpu.sh` |
| **금지** | 호스트 `python3` 직접 실행 |

```bash
bash scripts/run_kaggle_gl_download_gpu.sh
bash scripts/run_preprocess_enhanced_gpu.sh
tail -f preprocess_enhanced.log
```

### 컨테이너 마운트 규칙

| 용도 | 호스트 | 컨테이너 |
|------|--------|----------|
| MEDI 코드 | `$REPO` | `/workspace` |
| DR 데이터 | `$REPO/data` | `/data_dr` |
| GL/AMD/Multi | `$DATASET_ROOT` | `/dataset` |
| Kaggle 키 | `~/.kaggle` | `/root/.kaggle:ro` |

### Kaggle 데이터 다운로드 (GPU)

```bash
docker run --rm \
  -v ~/.kaggle:/root/.kaggle:ro \
  -v $DATASET_ROOT:/dataset \
  medi-train:gpu \
  bash -c 'pip install kaggle -q && kaggle datasets download -d ... -p /dataset/Glaucoma_extra2/G1020 --unzip'
```

---

## 이미지 정책

| 이미지 | 용도 | 서버 | 유지 |
|--------|------|------|------|
| **medi-train:gpu** | CNN 멀티태스크 훈련 (v10/v10c) | GPU `192.168.0.23` | ✅ **유지** · DockerHub `sangkny/medi-train:gpu-v1.0` |
| **medi-train:cpu** | CPU 스모크·manifest 검증 | 개발 PC / GPU | ✅ · DockerHub `sangkny/medi-train:cpu-v1.0` |
| **projects-medi-iot-api** | MEDI API (`medi-iot-api-dev`) | 개발 PC | ✅ **유지** |
| **projects-dashboard** | Portal/Admin (`dashboard-dev`) | 개발 PC | ✅ **유지** |
| ~~medi-train:retfound~~ | RETFound 실험 | GPU | ❌ **삭제** (2026-06-09) |

**원칙**

1. **추가 이미지 금지** — 새 기능은 기존 `medi-train:gpu` / `medi-iot-api-dev` 재활용
2. **`latest` 태그 금지** (MEDI 훈련) — `medi-train:gpu` 등 명시적 태그만 사용
3. **무계획 `docker build` 금지** — Dockerfile 변경 시 ch44·HANDOVER에 사유 기록

---

## DockerHub 백업 정책 (2026-06-11)

| 규칙 | 설명 |
|------|------|
| **신규 이미지** | `docker build` 직후 **즉시** `docker push sangkny/...` |
| **버전 태깅** | `v{major}.{minor}` — major: CUDA/PyTorch, minor: 패키지 |
| **삭제 전 확인** | `docker manifest inspect sangkny/이미지:태그` → 0이면 안전 삭제 |
| **로컬 alias** | pull 후 `docker tag sangkny/medi-train:gpu-v1.0 medi-train:gpu` |
| **builder prune** | `docker builder prune -f` — **root 권한** 필요할 수 있음 |

**복원 (GPU)**

```bash
docker pull sangkny/medi-train:gpu-v1.0
docker tag sangkny/medi-train:gpu-v1.0 medi-train:gpu
```

상세: `docs/DOCKER-REGISTRY.md`

---

## 서버별 역할

| 환경 | 실행 방식 | 포트 |
|------|-----------|------|
| **개발 PC** | `docker compose -f docker-compose.dev.yml` | MEDI **8001** · Dashboard **8090/dashboard/** · Vite **5174** |
| **GPU 서버** | `bash scripts/start_v10_train.sh` (`docker run --rm --gpus all`) | SSH only |

---

## 컨테이너 정책

| 규칙 | 설명 |
|------|------|
| `--rm` 필수 | 훈련 컨테이너는 종료 시 자동 삭제 |
| 동시 훈련 1개 | `medi-train:gpu` ancestor 컨테이너 **1개**만 |
| compose 우선 | 개발 PC API/DB/Redis는 **compose만** |
| 정기 정리 | GPU: `container prune` → `image prune` → `builder prune` (DockerHub 확인 후) |

---

## GPU 정리 기록 (2026-06-11)

| 항목 | 조치 |
|------|------|
| Build cache | **43.6GB → 0** (`builder prune`, root) |
| 미사용 이미지 | DockerHub 백업 확인 후 삭제 |
| **정리 후 디스크** | 이미지 **54.86GB** + 볼륨 6.24GB |
| **절약** | **~149GB** |
| 유지 (MEDI) | `medi-train:gpu` (9.66GB), `medi-train:cpu` (2.63GB) |

---

## 데이터 볼륨 마운트 (훈련)

| 호스트 (GPU) | 컨테이너 | 내용 |
|--------------|----------|------|
| `$REPO/data` | `/data_dr:ro` | DR `resized_cache/` |
| `$DATASET_ROOT` | `/dataset:ro` | GL/AMD/MYO/Multi `resized_cache/` |
| `$REPO` | `/workspace` | 코드 · `models/retinal_v4.pt` |

---

## 금지 사항

- 개발 PC에서 GPU 훈련 컨테이너 장기 실행
- v10 계열 동시 훈련 2개 이상
- 훈련 로그 없이 백그라운드 `docker run` (`$OUTPUT/train.log` 필수)
- ONNX/`.pt`를 git에 커밋
- DockerHub 미백업 이미지의 일괄 `docker image prune -a`

---

## 관련 문서

- `docs/DOCKER-REGISTRY.md` — 전체 이미지 목록 · 복원 명령어
- `book/part7/ch44-v10-multitask-architecture.md` §44.8
- `scripts/gpu_verify_v10b_env.sh`
- `CURSOR_HANDOVER.md`
