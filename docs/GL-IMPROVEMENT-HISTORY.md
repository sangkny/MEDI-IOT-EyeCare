# GL AUC 개선 이력

fast mode GL AUC 목표: **0.900+** (v10c 단독 baseline 0.835 · **앙상블로 달성**)

## v10~v13 전체 시리즈 최종 비교 (2026-06-20 확정)

| 버전 | GL AUC | composite | 방법 | 마스크 GL% | 상태 |
|------|--------|-----------|------|-----------|------|
| v10 | 0.804 | 0.8818 | resized_cache, 기본 | — | 참조 |
| v10b | 0.841 | 0.8726 | gl_w=0.35 | — | ❌ |
| **v10c** | **0.835** | **0.8842** | gl_w=0.28 | — | ✅ **운영** |
| v10d | 0.833 | 0.8793 | GL증강+오버샘플 | — | ❌ |
| v10e | 0.821 | 0.8790 | +extra2 | — | ❌ |
| v10f | 0.783 | 0.8397 | v2_cache only | — | ❌ |
| v12 | 0.829 | 0.8719 | +Disc/Cup seg_head | 8.7% | ❌ |
| **v13** | 0.829 | 0.8798 | +seg_head Plan B (G1020+ORIGA GT) | **14.2%** | ❌ |
| v10c+ensemble | 0.900+ | 0.8842 | v10c+glaucoma_v2 | — | ✅ **운영** |

## 전체 실험 결론 (2026-06-20 · **종료**)

1. **v10c** (composite=**0.8842**, GL=**0.835**) — 모든 단일 모델 중 **최우수** → **운영 유지**
2. **v2_cache 훈련** (v10f) — 도메인 불일치로 composite·GL **대폭 하락**
3. **extra2 분류 데이터** (v10e) — GL 개선 **없음**
4. **Disc/Cup seg 보조 헤드** (v12/v13) — composite **소폭** 개선, GL AUC **거의 불변**
   - v12→v13: 마스크 8.7%→14.2%, composite **+0.0079**, GL **0.829→0.829**
   - segDice **0.978~0.980** — seg_head 학습은 성공, GL 직접 전달은 **미약**
   - composite 개선분은 주로 **QWK/AMD/mAUC** 등 다른 task 기여
5. **SAM/OSAM pseudo-mask** — Phase1 Dice 0.544, Phase2 Dice 0.272 → **채택 안 함**
6. **GL 개선**은 **앙상블**(v10c+glaucoma_v2)로 달성 → fast GL **0.900+**

### 종합 판정

**Disc/Cup 보조 세그멘테이션 접근(v12/v13)은 composite를 소폭 개선했으나 GL AUC 자체나 v10c 대비 우위를 만들지 못함.**  
마스크 비율을 **70%+** 수준으로 끌어올리지 않는 한 추가 시도 ROI 낮음 → **이 방향 deprioritize**.  
임상 데이터 축적 후 재검토.

## v13 상세 (Plan B · 2026-06-20)

| 항목 | 값 |
|------|-----|
| manifest | `unified_v13.json` (plan_b) |
| 마스크 | G1020 **1,020** + ORIGA **650** = **1,670** (**14.2%** GL) |
| best_composite | **0.8798** (ep33, early_stop ep45) |
| GL AUC | **~0.829** |
| segDice | **0.980** |
| seg_weight | 0.05 |
| GPU peak mem | **7.69GB** |
| 상태 | ❌ **미배포** |
| meta | `models/retinal_v13/best.meta.json` |
| SSOT | `docs/V13-PLAN-B.md` · `docs/V13-SAM-PSEUDO-MASK.md` |

## v12 상세 (2026-06-19)

| 항목 | 값 |
|------|-----|
| manifest | `unified_v12.json` |
| best_composite | **0.8719** |
| GL AUC | **~0.829** |
| segDice | **0.978** |
| 마스크 GL% | **8.7%** |
| 상태 | ❌ **미배포** |
| meta | `models/retinal_v12/best.meta.json` |

## v10f / v10e (참고)

| 버전 | composite | GL | 비고 |
|------|-----------|-----|------|
| v10f | 0.8397 | ~0.783 | v2_cache 100% — pretrained 도메인 불일치 |
| v10e | 0.8790 | 0.821 | extra2 무효 |

## 운영 확정 (변경 없음)

| 구성 | 지표 | 상태 |
|------|------|------|
| v10c fast | composite **0.8842** · GL **0.835** | ✅ |
| v10c + glaucoma_v2 앙상블 | fast GL **0.900+** | ✅ |
| precise (glaucoma_v2) | AUC **0.946** | ✅ |

## 향후 GL 개선 (2026-06-20 이후)

| 우선순위 | 방향 | 비고 |
|----------|------|------|
| 1 | SaMD 임상 데이터 | 장기 현실적 |
| 2 | v10c GL head fine-tuning | 중기 검토 |
| ~~3~~ | ~~SAM pseudo-mask v13~~ | ❌ OSAM/BBox 품질 미달 → Plan B도 v10c 미달 |
| ~~4~~ | ~~seg 보조 헤드~~ | ❌ **deprioritize** (마스크 70%+ 전까지) |

## GPU 캐시 정리 계획

| 경로 | 조치 |
|------|------|
| `/dataset/v2_cache` | 삭제 예정 |
| `/dataset/enhanced_cache` | 삭제 예정 |
| `/dataset/resized_cache` | **유지** (v10c 운영) |

## 앙상블 (Part D) — 운영

- 불확실 구간: v10c GL prob **0.30 ~ 0.70**
- 가중치: v10c **0.35** / glaucoma_v2 **0.65**
- E2E sklee: v10c **0.605** → 앙상블 **0.725** (`ensemble_v10c_v2`)
