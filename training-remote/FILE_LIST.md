# 원격 학습 관련 파일 목록 (레거시)

> **SSOT는 [`../training/`](../training/README.md)** 입니다. 신규 작업은 `training/docker-compose.train.yml` 을 사용하세요.

## Docker (CPU / GPU)

| 파일 | 설명 |
|------|------|
| `Dockerfile.cpu` | CPU 전용 학습 이미지 |
| `Dockerfile.gpu` | NVIDIA CUDA 12.4 학습 이미지 |
| `docker-compose.cpu.yml` | CPU compose (`medi-dr-train:cpu`) |
| `docker-compose.gpu.yml` | GPU compose (`medi-dr-train:gpu`) |
| `requirements-train-docker.txt` | 이미지 내 pip (torch 제외) |
| `docker-entrypoint.sh` | 엔트리포인트 · `check` |
| `docker-train.sh` / `docker-train.ps1` | 래퍼 |
| `env.train.example` | ARCH, BATCH, EPOCHS |

## 필수 (번들에 포함)

| 파일 | 역할 |
|------|------|
| `services/retinal_cnn.py` | EfficientNet/MSEF-Net, CLAHE, DR 라벨·ICD 매핑 |
| `scripts/generate_synthetic_fundus.py` | 합성 1,000장 (OOM 시 데이터 생성은 로컬/원격 소량 가능) |
| `scripts/build_messidor2_manifest.py` | `data_dir` → `manifest.json` |
| `scripts/download_datasets.py` | Kaggle/수동 안내·합성 fallback |
| `scripts/train_retinal.py` | 학습·체크포인트·meta ( `--skip-onnx` 권장) |
| `scripts/export_onnx.py` | `.pt` → `.onnx` (메모리 여유 시 별도 실행) |
| `scripts/eval_messidor.py` | QWK, AUC, confusion matrix |
| `training-remote/README.md` | 본 가이드 |
| `training-remote/requirements-train.txt` | pip 의존성 |
| `training-remote/run_*.sh` | 원샷 파이프라인 |

## 산출물 (Git 제외, scp로 회수)

| 파일 | 크기(대략) |
|------|------------|
| `models/retinal_v2.pt` | B0 ~16MB / B4 ~70MB |
| `models/retinal_v2.onnx` | B0 ~20MB / B4 ~70MB |
| `models/retinal_v2.meta.json` | <1KB |
| `reports/eval_*.json` | 평가 기록 |
| `data/synthetic_manifest.json` | 학습에 사용한 매니페스트 사본 |

## 본 프로젝트 연동

| 파일 | 설정 |
|------|------|
| `projects/docker-compose.dev.yml` | `MEDI_CNN_MODEL_PATH`, `MEDI_INFERENCE_BACKEND=cnn` |
| `services/inference_router.py` | ONNX Runtime 추론 |
| `models/README.md` | MinIO·모델 배치 |
