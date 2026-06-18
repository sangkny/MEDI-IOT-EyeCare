# GL AUC 개선 이력

fast mode GL AUC 목표: **0.900+** (v10c 단독 baseline 0.835 · **앙상블로 달성**)

## v10 시리즈 + v12 최종 비교 (2026-06-19 확정)

| 버전 | GL AUC | composite | 방법 | 상태 |
|------|--------|-----------|------|------|
| v10 | 0.804 | 0.8818 | resized_cache, 기본 | 참조 |
| v10b | 0.841 | 0.8726 | resized_cache, gl_w=0.35 | 미배포 |
| v10c | **0.835** | **0.8842** | resized_cache, gl_w=0.28 | ✅ **운영** |
| v10d | 0.833 | 0.8793 | GL증강+오버샘플 | ❌ |
| v10e | 0.821 | 0.8790 | +extra2 데이터 | ❌ |
| v10f | 0.783 | 0.8397 | v2_cache only | ❌ |
| **v12** | 0.829 | 0.8719 | +Disc/Cup seg_head | ❌ |
| v10c+ensemble | 0.900+ | 0.8842 | v10c+glaucoma_v2 | ✅ **운영** |

## 전체 실험 결론 (2026-06-19)

1. **v10c** (composite=**0.8842**, GL=**0.835**) 최우수 → **계속 운영**
2. **v2_cache 전처리 훈련** — 성능 크게 하락 (v10f composite 0.8397, GL ~0.783)
   - **원인**: `retinal_v4.pt` pretrained가 **CLAHE+직접 resize**로 학습됨
   - v2 (**CenterCrop+CLAHE+UnsharpRGB**)와 **도메인 불일치** → pretrained transfer 효과 감소
3. **extra2 분류 데이터 추가** — 효과 없음 (v10e GL 0.821)
4. **v12 Disc/Cup seg 보조 헤드** — **미배포** (composite **0.8719**, GL **~0.829**)
   - segDice **0.978** → seg_head 자체는 완벽 학습
   - GL 미향상 원인: **마스크 커버리지 부족** (GL 샘플 중 **8.7%**만 seg supervision)
5. **GL 개선**은 **앙상블**(v10c+glaucoma_v2)로 달성 → fast GL AUC **0.900+**

### v12 상세 (2026-06-19)

| 항목 | 값 |
|------|-----|
| manifest | `unified_v12.json` |
| best_composite | **0.8719** |
| GL AUC | **~0.829** |
| segDice | **0.978** |
| seg_weight | 0.05 |
| GPU peak mem | **7.69GB** (unfreeze 후 안전) |
| 마스크 커버리지 | 1,020 / 27,546 (**3.7%**) |
| GL 중 마스크 | 1,020 / 11,725 (**8.7%**) |
| 상태 | ❌ **미배포** (v10c 대비 모든 지표 하락) |
| meta | `models/retinal_v12/best.meta.json` |

**실패 원인**: backbone이 disc/cup 위치를 학습하기에 마스크 **절대량·비율** 모두 부족. 보조 태스크 신호가 backbone 표현에 충분히 전달되지 않음.

**교훈**: 마스크 데이터가 GL 샘플의 **30~50% 이상**이어야 보조 seg 효과 기대 가능. 현재 **8.7%** → 효과 미미.

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

## 향후 GL 개선 방향 (v12 이후, 2026-06-19)

**v10c+앙상블 운영 유지**. seg 보조 태스크는 **마스크 충분 확보 후** 재시도.

| 옵션 | 내용 | 현실성 |
|------|------|--------|
| **A** | ORIGA Masks_Square(**651**) 추가 → 마스크 **1,671** (**14.3%**) | ⚠️ 여전히 낮은 비율 |
| **B** | RIM-ONE disc/cup 마스크 탐색 (기존 보유 데이터) | 중기 |
| **C** | **SAM pseudo-mask** → GL **~100%** → **v13** | ✅ **최우선 (진행 중)** |
| **D** | v10c GL head만 fine-tuning | 중기 검토 |
| **E** | SaMD 임상 데이터 fine-tuning | ✅ 장기 현실적 |

> v13 파이프라인: `docs/V13-SAM-PSEUDO-MASK.md` · Option 3(glaucoma_v2 ONNX) **분류만** → 불가

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
