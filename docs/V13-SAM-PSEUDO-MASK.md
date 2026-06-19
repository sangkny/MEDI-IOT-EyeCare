# v13 SAM Pseudo-Mask — Disc/Cup 세그멘테이션

## 1. 배경

**v12 교훈**: GL 마스크 **8.7%** → segDice 0.978이나 GL/composite v10c 미달.

## 2. Option 검토

| Option | 결과 |
|--------|------|
| glaucoma_v2 ONNX | ❌ 분류만 |
| Phase 1 BBox SAM | ❌ mean Dice **0.544** |
| Phase 2 OSAM | ❌ mean Dice **0.2723** — pseudo-mask **채택 안 함** |
| **Plan B (GT)** | ✅ composite **0.8798** — v10c 미달로 **미배포** |

## 3. Phase 1 — BBox SAM (실패)

| 지표 | 값 |
|------|-----|
| mean Dice | **0.544** |
| Dice < 0.70 | **83%** |
| 판정 | pseudo-mask 품질 부족 → 본 훈련 **보류** |

## 4. Phase 2 — OSAM-Fundus (DINOv2 + SAM)

```
G1020 GT 80장 참조 풀 → DINOv2 disc/cup/bg prototype
타겟 patch cosine matching → SAM box prompts (고해상도 안저)
leave-one-out self-test (10장) → mean Dice ≥ 0.80 목표
```

| 구성 | 설명 |
|------|------|
| DINOv2 | `dinov2_vits14` (TITAN X 12GB) — hub 로드 ✅ |
| SAM | ViT-B + **DINO-guided box** (point-only는 고해상도에서 실패) |
| 참조 | G1020 GT 상위 **80**장 (면적 outlier 제외) |
| self-test | 타겟은 참조 풀에서 **제외** (leave-one-out) |

코드: `services/osam_fundus.py` · `scripts/generate_pseudo_masks_sam.py --method osam`

### Phase 2 결과 (GPU 192.168.0.23 · 2026-06-19)

| 시도 | mean Dice | median | pass@0.80 | 판정 |
|------|-----------|--------|-----------|------|
| point prompts (v1) | **0.0445** | 0.0099 | 0/10 | cup 84% 과대 — 2423×3004에서 SAM point 실패 |
| DINO box + 1024px (`bfe6e40`) | **0.2723** | 0.2674 | 0/10 | Phase 1(0.544)보다 **낮음** |

**Plan B 전환 이유**: OSAM pseudo-mask가 품질 기준(≥0.80) 및 Phase 1 BBox SAM보다 열위 → `all_gl` pseudo 생성 **실행 안 함**. 기존 ORIGA Masks_Square GT 활용으로 전환.

## 5. Plan B — G1020 + ORIGA GT (최종 채택)

| 소스 | 장수 | 경로 |
|------|------|------|
| G1020 GT | 1,020 | `disc_cup_masks/G1020/` |
| ORIGA Masks_Square | 650 | `disc_cup_masks/ORIGA/` |
| **합계** | **1,670** | GL 11,725 중 **14.2%** |

### v13 Plan B 훈련 결과 (2026-06-20)

| 지표 | v12 | v13 (Plan B) | v10c (운영) |
|------|-----|--------------|-------------|
| composite | 0.8719 | **0.8798** | **0.8842** |
| GL AUC | ~0.829 | **~0.829** | **0.835** |
| segDice | 0.978 | **0.980** | — |
| 마스크 GL% | 8.7% | **14.2%** | — |
| 상태 | ❌ | ❌ **미배포** | ✅ **운영** |

- best_composite **0.8798** (ep33, early_stop ep45)
- seg_weight **0.05** · GPU peak **7.69GB**
- meta: `models/retinal_v13/best.meta.json`

**관찰**: 마스크 8.7%→14.2%로 composite **+0.0079** (v12→v13). GL AUC는 거의 변화 없음 → composite 개선은 주로 QWK/AMD/mAUC 기여.

## 6. 종합 결론 (2026-06-20)

1. **vanilla SAM / OSAM pseudo-mask** — 품질 미달, v13 본훈련에 **미사용**
2. **Plan B (GT 마스크)** — composite 소폭 개선, **v10c 대체 불가**
3. **마스크 비율 증가**는 방향성 있으나 **70%+ 없이 GL 직접 개선 한계**
4. **운영 유지**: v10c + glaucoma_v2 앙상블 (변경 없음)
5. **GL seg 보조 실험(v12/v13) deprioritize** — ROI 낮음, 임상 데이터 축적 후 재검토

## 7. 주의

- pseudo-mask `.png` · `*.pt` → git 제외
- Docker 중첩 run 금지
- SSOT Plan B: `docs/V13-PLAN-B.md`
