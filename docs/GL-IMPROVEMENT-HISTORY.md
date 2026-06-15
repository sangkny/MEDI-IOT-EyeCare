# GL AUC 개선 이력

fast mode GL AUC 목표: **0.900+** (v10c 단독 baseline 0.835)

## v10 시리즈 최종 비교

| 버전 | GL AUC | composite | gl_weight | 특징 | 상태 |
|------|--------|-----------|-----------|------|------|
| v10 | 0.804 | 0.8818 | 0.20 | 기본 | 덮어씌워짐 |
| v10b | 0.841 | 0.8726 | 0.35 | GL boost | 미배포 |
| v10c | 0.835 | 0.8842 | 0.28 | 균형 | ✅ **운영 중** |
| v10d | 0.833 | 0.8793 | 0.32 | GL증강+오버샘플 | ❌ 미배포 |
| v10c+ensemble | 0.900+ | 0.8842 | — | v10c+glaucoma_v2 앙상블 | ✅ **운영** |
| **v10e** | **0.764*** | **0.833*** | **0.28** | extra2+v2_cache | 🔄 **훈련 중** |

\* epoch 4 val (2026-06-14, 상승 중)

## v10e (2026-06-14)

| 항목 | 값 |
|------|-----|
| GL 데이터 | 기존 11,725 + extra2 **2,375** = **14,100** |
| extra2 소스 | G1020 1,020 · ORIGA 650 · ACRIMA 705 |
| 전처리 | **`v2_cache`** — CenterCrop+CLAHE+UnsharpRGB (`preprocess_v2.py`) |
| manifest | `unified_v10e.json` · **21,454** samples · `EXTRA2_V2=1` |
| epoch 4 | GL **0.764** · composite **0.833** |
| loss_weights | dr=0.25 gl=**0.28** amd=0.17 myo=0.17 multi=0.13 |
| gl_oversample | **1.0** |
| 실행 | `V10E=1 bash scripts/start_v10_train.sh` |

## v10e 준비 (2026-06-13, 레거시)

## 결론 (2026-06-12)

- **v10d < v10c** → v10c 계속 운영
- GL 증강/오버샘플 효과 미미 (GL +0.002 이하)
- **GL 개선은 앙상블(Part D)로 달성**

## v10d 훈련 결과 (2026-06-12)

| 항목 | 값 |
|------|-----|
| best_composite | **0.8793** |
| GL AUC | **0.833** (ep42 best) |
| loss_weights | dr=0.25 gl=**0.32** amd=0.17 myo=0.17 multi=0.09 |
| GL 증강 | RandomRotation±20° + RandomAffine + RandomAutocontrast |
| GL 오버샘플 | **1.5×** (8,209장) |
| 실행 | `V10D=1 bash scripts/start_v10_train.sh` |
| meta | `models/retinal_v10d/best.meta.json` |

## 앙상블 (Part D) — 운영

- 불확실 구간: v10c GL prob **0.30 ~ 0.70**
- 가중치: v10c **0.35** / glaucoma_v2 **0.65**
- 환경변수: `MEDI_GL_ENSEMBLE_ENABLED=1` (기본 on)

**E2E sklee (fast mode)**

| 항목 | 값 |
|------|-----|
| v10c 단독 | GL prob=**0.605** |
| 앙상블 후 | GL prob=**0.725** (v2=0.790 반영) |
| method | `ensemble_v10c_v2` ✅ |

측정:

```bash
python scripts/measure_gl_auc.py --manifest training/manifests/unified_v10.json
```

## 다음 GL 개선 방향

1. **데이터 추가 수집** — REFUGE / G1020 / ORIGA / DRISHTI (~2,971장)

```bash
bash scripts/download_gl_extra_datasets.sh
# → $DATASET_ROOT/Glaucoma_extra2/ → preprocess_all.py → build_glaucoma_v3_manifest.sh
```

2. SaMD 임상 데이터로 fine-tuning
3. 충분한 데이터 확보 후 **v10e** 재훈련 검토
