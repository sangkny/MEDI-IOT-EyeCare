# GL AUC 개선 이력

fast mode GL AUC 목표: **0.900+** (v10c 단독 baseline 0.835)

## v10 시리즈 최종 비교

| 버전 | GL AUC | composite | gl_weight | 특징 | 상태 |
|------|--------|-----------|-----------|------|------|
| v10 | 0.804 | 0.8818 | 0.20 | 기본 | 덮어씌워짐 |
| v10b | 0.841 | 0.8726 | 0.35 | GL boost | 미배포 |
| v10c | 0.835 | 0.8842 | 0.28 | resized_cache · 균형 | ✅ **운영 중** |
| v10d | 0.833 | 0.8793 | 0.32 | GL증강+오버샘플 | ❌ 미배포 |
| v10c+ensemble | 0.900+ | 0.8842 | — | v10c+glaucoma_v2 앙상블 | ✅ **운영** |
| v10e | 0.821 | 0.8790 | 0.28 | resized_cache + extra2 (v2_cache 미반영) | ❌ 미배포 |
| **v10f** | **0.781** | **0.8397** | **0.28** | **v2_cache only** (extra2 제외) | ❌ **미배포** |

## 결론 (2026-06-17 — Option B 완료)

| 비교 | v10c (resized_cache) | v10f (v2_cache) | Δ |
|------|----------------------|-----------------|-----|
| composite | **0.8842** | 0.8397 | **−0.0445** |
| GL AUC (best composite ep) | **0.835** | 0.781 | **−0.054** |

- **v10f < v10c** → **v10c 계속 운영**
- **훈련용 v2_cache 교체는 채택하지 않음** (CenterCrop+CLAHE+Unsharp 단독은 val 지표 하락)
- v10e( extra2 )·v10f( v2_cache ) 모두 v10c 미달 → 데이터·전처리 변수 분리 실험 종료
- **GL 개선 경로**: 앙상블(v10c+glaucoma_v2) 유지 · 실시간 `?preprocess=v2` API는 추론용으로 별도 유지

## v10f (Option B — 2026-06-17 완료)

목적: extra2 변수 제거 · **v2 전처리 효과만** 분리 측정.

| 항목 | 값 |
|------|-----|
| manifest | `unified_v10f.json` · v2_cache **100%** (27,546/27,546) |
| 생성 | `scripts/build_v10f_manifest.py` |
| train/val | 19,814 / 3,863 |
| best composite | **0.8397** (ep34 · GL=0.7806) |
| peak GL | 0.7831 (ep45) |
| early-stop | ep46 (patience=12) |
| loss_weights | dr=**0.28** gl=**0.28** amd=0.18 myo=0.18 multi=0.08 |
| 산출물 | GPU `models/retinal_v10f/best.pt` (git 제외) |
| 실행 | `V10F=1 bash scripts/start_v10_train.sh` |

## v10e (2026-06-14)

| 항목 | 값 |
|------|-----|
| GL 데이터 | 기존 11,725 + extra2 **2,375** = **14,100** |
| extra2 소스 | G1020 1,020 · ORIGA 650 · ACRIMA 705 |
| 전처리 | **resized_cache** (+extra2). v2_cache는 **미반영** |
| manifest | `unified_v10e.json` (extra2 merge) |
| 결과 | GL **0.821** · composite **0.8790** |
| loss_weights | dr=0.25 gl=**0.28** amd=0.17 myo=0.17 multi=0.13 |
| 실행 | `V10E=1 bash scripts/start_v10_train.sh` |

## v10d 훈련 결과 (2026-06-12)

| 항목 | 값 |
|------|-----|
| best_composite | **0.8793** |
| GL AUC | **0.833** (ep42 best) |
| loss_weights | dr=0.25 gl=**0.32** amd=0.17 myo=0.17 multi=0.09 |
| GL 증강 | RandomRotation±20° + RandomAffine + RandomAutocontrast |
| GL 오버샘플 | **1.5×** (8,209장) |
| 실행 | `V10D=1 bash scripts/start_v10_train.sh` |

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

## 다음 GL 개선 방향

1. **앙상블·glaucoma_v2** 경로 유지 (fast GL 0.900+ 달성)
2. SaMD 임상 데이터 fine-tuning (병원 협력 후)
3. v2_cache + extra2 **동시** 실험(v10g)은 백로그 — v10e/v10f 단독 실험 종료
4. `resized_cache` 삭제는 v10c ONNX 운영 재확인 후
