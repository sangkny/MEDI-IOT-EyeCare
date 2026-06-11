# GPU 서버 Docker 이미지 레지스트리 (2026-06-11 기준)

> SSOT: GPU `smartvisionglobal@192.168.0.23` · DockerHub `sangkny`  
> 정책: `docs/DOCKER-POLICY.md` · 책: `book/part7/ch44-v10-multitask-architecture.md` §44.8

---

## 현재 이미지 목록

### 훈련 이미지 (MEDI-IOT 전용)

| 로컬 이미지 | DockerHub 백업 | 크기 | 용도 |
|------------|----------------|------|------|
| `medi-train:gpu` | `sangkny/medi-train:gpu-v1.0` | 9.66GB | CNN 훈련 (CUDA) |
| `medi-train:cpu` | `sangkny/medi-train:cpu-v1.0` | 2.63GB | CPU 훈련 백업 |

### 프로젝트 이미지 (타 프로젝트)

| 이미지 | 크기 | 용도 | DockerHub |
|--------|------|------|-----------|
| `sangkny/yolov11_pytorch:latest` | 19.1GB | fire_yolo11 훈련 | ✅ |
| `sangkny/yolov8_ubuntu_torch2.2_cuda12.1_py3.8:20240509` | 13.9GB | YOLOv8 훈련 | ✅ |
| `sangkny/yolov8_no_source_ubuntu_torch2.2_cuda12.1_py3.8:20240509` | 11.2GB | YOLOv8 소스없음 | ✅ |
| `sangkny/darknet:10.1-cudnn7-devel-ubuntu16.04` | 6.9GB | Darknet 레거시 | ✅ |
| `sangkny/tacr-eval:20251009_1531` | 1.35GB | TACR 평가 | ✅ |
| `sangkny/tacr-eval:latest` | 1.35GB | TACR 평가 | ✅ |
| `sangkny/tacr-eval:20250831_2212` | 832MB | TACR 평가 | ✅ |
| `sangkny/tacr-eval:20250826_0625` | 598MB | TACR 평가 | ✅ |
| `python:3.11-slim` | 125MB | 범용 | ✅ |

---

## DockerHub 백업 현황

모든 이미지가 DockerHub **`sangkny`** 계정에 백업됨 → 로컬 삭제 후 언제든 `docker pull` 가능.

---

## 이미지 복원 명령어

### MEDI-IOT 훈련 환경 복원

```bash
# medi-train:gpu 없을 때:
docker pull sangkny/medi-train:gpu-v1.0
docker tag sangkny/medi-train:gpu-v1.0 medi-train:gpu

# medi-train:cpu 없을 때:
docker pull sangkny/medi-train:cpu-v1.0
docker tag sangkny/medi-train:cpu-v1.0 medi-train:cpu
```

### 훈련 시작 전 체크

```bash
ssh smartvisionglobal@192.168.0.23 "docker images | grep medi-train"
```

없으면:

```bash
ssh smartvisionglobal@192.168.0.23 "
docker pull sangkny/medi-train:gpu-v1.0 &&
docker tag sangkny/medi-train:gpu-v1.0 medi-train:gpu
"
```

---

## 정리 정책

### 안전한 정리 (항상 가능)

```bash
docker container prune -f   # 종료 컨테이너
docker image prune -f       # dangling 이미지
docker builder prune -f     # 빌드 캐시 (root 권한 필요)
```

### DockerHub 확인 후 삭제

```bash
# 삭제 전 DockerHub 존재 확인:
docker manifest inspect sangkny/이미지명:태그
# returncode=0이면 DockerHub에 있음 → 안전 삭제 가능
```

### 절대 삭제 금지 (훈련 중)

훈련 컨테이너 실행 중에는 베이스 이미지 삭제 불가.

```bash
docker ps | grep medi-train   # 확인 후 진행
```

---

## 이미지 업데이트 · 버전 관리

훈련 환경 변경 시 새 버전 태깅:

```bash
docker tag medi-train:gpu sangkny/medi-train:gpu-v1.1
docker push sangkny/medi-train:gpu-v1.1
```

| 규칙 | 설명 |
|------|------|
| **major** | 환경 대규모 변경 (CUDA, PyTorch 메이저) |
| **minor** | 패키지 추가/업데이트 |

형식: `v{major}.{minor}` (예: `gpu-v1.0`, `gpu-v1.1`)

---

## 디스크 사용량 현황 (2026-06-11)

| 시점 | 이미지 | Build cache | 볼륨 | 합계 |
|------|--------|-------------|------|------|
| **정리 전** | 159.9GB | 43.6GB | 6.24GB | **~203.5GB** |
| **정리 후** | 54.86GB | 0B | 6.24GB | **~61GB** |
| **절약** | — | — | — | **~149GB** |

---

## 관련 문서

- `docs/DOCKER-POLICY.md` — 운영 정책 · DockerHub push 규칙
- `scripts/start_v10_train.sh` — `--rm` 훈련 컨테이너
- `CURSOR_HANDOVER.md` — GPU 스냅샷
