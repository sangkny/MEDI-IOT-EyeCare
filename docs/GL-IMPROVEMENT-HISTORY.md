# GL AUC 개선 이력

fast mode GL AUC 목표: **0.900+** (v10c 단독 baseline 0.835 · **앙상블로 달성**)

## v10 시리즈 최종 비교 (2026-06-17 확정)

| 버전 | GL AUC | composite | 전처리 | 데이터 | 상태 |
|------|--------|-----------|--------|--------|------|
| v10 | 0.804 | 0.8818 | resized_cache | 기본 | 참조 |
| v10b | 0.841 | 0.8726 | resized_cache | gl_w=0.35 | 미배포 |
| v10c | 0.835 | 0.8842 | resized_cache | gl_w=0.28 | ✅ **운영** |
| v10d | 0.833 | 0.8793 | resized_cache | GL증강+오버샘플 | 미배포 |
| v10e | 0.821 | 0.8790 | resized_cache | +extra2 | 미배포 |
| v10f | 0.783 | 0.8397 | v2_cache | v2전처리 only | ❌ 미배포 |
| v10c+ensemble | 0.900+ | 0.8842 | — | v10c+glaucoma_v2 | ✅ **운영** |

## 전체 실험 결론 (2026-06-17)

1. **v10c** (composite=**0.8842**, GL=**0.835**) 최우수 → **계속 운영**
2. **v2_cache 전처리 훈련** — 성능 크게 하락 (v10f composite 0.8397, GL ~0.783)
   - **원인**: `retinal_v4.pt` pretrained가 **CLAHE+직접 resize**로 학습됨
   - v2 (**CenterCrop+CLAHE+UnsharpRGB**)와 **도메인 불일치** → pretrained transfer 효과 감소
3. **extra2** (G1020+ORIGA+ACRIMA) 추가 — 효과 없음 (v10e GL 0.821)
   - **원인 추정**: 라벨 신뢰도 또는 공개 데이터셋 분포 차이
4. **GL 개선**은 **앙상블**(v10c+glaucoma_v2)로 달성 → fast GL AUC **0.900+**

### v10f 상세

| 항목 | 값 |
|------|-----|
| manifest | `unified_v10f.json` (v2_cache only, extra2 제외) |
| v2_cache 교체율 | **100%** (27,546/27,546) |
| best_composite | **0.8397** (ep34) |
| GL AUC | **~0.783** (peak ep45 0.7831) |
| early-stop | ep46 |
| 실행 | `V10F=1 bash scripts/start_v10_train.sh` |

### v10e 상세

| 항목 | 값 |
|------|-----|
| manifest | `unified_v10e.json` (extra2 merge) |
| GL 데이터 | 11,725 + extra2 **2,375** |
| 결과 | GL **0.821** · composite **0.8790** |
| 한계 | v2_cache 미반영 → v10f로 분리 검증 완료 |

## 운영 확정

| 구성 | 지표 | 상태 |
|------|------|------|
| v10c fast | composite **0.8842** · GL **0.835** | ✅ |
| v10c + glaucoma_v2 앙상블 | fast GL **0.900+** | ✅ |
| precise (glaucoma_v2) | AUC **0.946** | ✅ |

## 향후 GL 개선 방향 (재검토)

**v2_cache / extra2 단독 방향은 포기** (v10e·v10f 실험으로 검증 완료).

| 옵션 | 내용 | 현실성 |
|------|------|--------|
| **A** | `retinal_v4.pt`를 **v2_cache**로 재학습 (기반 모델부터) | 시간·비용 큼 |
| **B** | v10c 기반 **GL head만** fine-tuning (glaucoma_v2 수준 AUC 목표) | 중기 검토 |
| **C** | **앙상블 유지** + SaMD 임상 데이터 fine-tuning | ✅ **가장 현실적** |
| **D** | **v12** Disc/Cup 보조 세그 헤드 (G1020 마스크) | 🔄 **진행 중** (2026-06-17) |

## v12 — 구조 변경 실험 (2026-06-17)

| 항목 | 내용 |
|------|------|
| 카테고리 | **구조 변경** (v10d/e/f의 입력·전처리 변경과 구분) |
| 백본 | EfficientNet-B4 (v10c 동일) |
| 추가 | disc/cup 세그 헤드 + CDR 계산 (`cdr_estimator.py`) |
| 데이터 | G1020 disc/cup 폴리곤 → `disc_cup_masks/` |
| manifest | `unified_v12.json` |
| loss | 기존 5-head + seg CE (weight **0.05**) |
| 상태 | 코드·smoke 준비 완료, 본 훈련 TBD |

> 상세: `docs/V12-DISC-CUP-SEGMENTATION.md`

## GPU 캐시 정리 계획

| 경로 | 조치 | 이유 |
|------|------|------|
| `/dataset/enhanced_cache` | **삭제 예정** | v1 레거시 |
| `/dataset/v2_cache` | **삭제 예정** | v10f 실패 · 훈련 불채택 |
| `/data_dr/v2_cache` | **삭제 예정** | 동일 |
| `/dataset/resized_cache` | **유지** | v10c 운영 중 |
| `/data_dr/resized_cache` | **유지** | v10c 운영 중 |

> 실시간 API `?preprocess=v2`는 추론 파이프라인용으로 **코드 유지**. 훈련 캐시만 정리.

## 앙상블 (Part D) — 운영

- 불확실 구간: v10c GL prob **0.30 ~ 0.70**
- 가중치: v10c **0.35** / glaucoma_v2 **0.65**
- `MEDI_GL_ENSEMBLE_ENABLED=1` (기본 on)

**E2E sklee (fast mode)**

| 항목 | 값 |
|------|-----|
| v10c 단독 | GL prob=**0.605** |
| 앙상블 후 | GL prob=**0.725** |
| method | `ensemble_v10c_v2` ✅ |
