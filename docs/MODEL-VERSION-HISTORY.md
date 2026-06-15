# Retinal 모델 버전 이력

| 버전 | 상태 | 특징 | gl_weight | GL 규모 | 날짜 |
|------|------|------|-----------|---------|------|
| v10 | 덮어씌워짐 | 기본 멀티태스크 | 0.20 | ~11,725 | 2026-05 |
| v10b | 미배포 | GL boost | 0.35 | ~11,725 | 2026-06 |
| v10c | ✅ 운영 | 균형 · 앙상블 base | 0.28 | ~11,725 | 2026-06 |
| v10d | ❌ 미배포 | GL증강+oversample | 0.32 | ~11,725 | 2026-06-12 |
| **v10e** | **훈련 중** | GL증강+extra2+**v2_cache** | **0.28** | **14,100** | **2026-06-14** |

## v10e 훈련 (2026-06-14)

| 항목 | 값 |
|------|-----|
| manifest | `unified_v10e.json` · **21,454** train samples |
| 전처리 | `v2_cache` (CenterCrop+CLAHE+UnsharpRGB) |
| epoch 4 (참고) | GL AUC **0.764** · composite **0.833** (상승 중) |
| loss_weights | dr=0.25 gl=**0.28** amd=0.17 myo=0.17 multi=0.13 |
| 실행 | `V10E=1 bash scripts/start_v10_train.sh` |

## v10e 준비 (2026-06-13)

- **manifest**: `training/manifests/unified_v10e.json` (unified_v10 + gl_extra2 2,375장)
- **전처리**: `v2_cache` (CenterCrop+CLAHE+Unsharp · `scripts/preprocess_v2.py`)
- **훈련**: `V10E=1 bash scripts/start_v10_train.sh` — batch=64, warmup=8, preprocess=none
- **출력**: `models/retinal_v10e`

```bash
bash scripts/run_preprocess_v2_gpu.sh
EXTRA2_V2=1 bash scripts/run_build_v10e_manifest_gpu.sh
V10E=1 bash scripts/start_v10_train.sh
```
