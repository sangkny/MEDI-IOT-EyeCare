# v13 Plan B — G1020 + ORIGA 실제 GT 마스크

## 배경

SAM/OSAM pseudo-mask 경로 실패 후 **실제 정답 마스크만** 사용.

| 소스 | 장수 | 경로 |
|------|------|------|
| G1020 GT | 1,020 | `disc_cup_masks/G1020/{stem}_mask.png` |
| ORIGA Masks_Square | 650 | `disc_cup_masks/ORIGA/{stem}_mask.png` |
| **합계** | **1,670** | GL 11,725 중 **~14.2%** |

## 실행 (GPU Docker)

```bash
bash scripts/run_build_v13_planb_gpu.sh
V13=1 bash scripts/start_v10_train.sh
```

## manifest

- 입력: `unified_v12.json`
- 출력: `unified_v13.json` (`plan_b: true`)
- `disc_cup_mask_source`: `gt_g1020` | `gt_origa`
- 매칭: 경로에 `g1020`/`origa` 포함 여부 (stem 충돌 방지)

## 훈련 결과 (2026-06-20)

| 항목 | 값 |
|------|-----|
| best_composite | **0.8798** (ep33) |
| early_stop | ep45 |
| GL AUC | **~0.829** (ep45 0.8296) |
| segDice | **0.980** |
| seg_weight | **0.05** |
| GPU peak mem | **7.69GB** |
| 판정 | ❌ **미배포** (v10c 0.8842 / GL 0.835 미달) |
| meta | `models/retinal_v13/best.meta.json` |

## v12 대비

| | v12 | v13 Plan B |
|--|-----|------------|
| composite | 0.8719 | **0.8798** (+0.0079) |
| GL AUC | ~0.829 | ~0.829 (변화 없음) |
| 마스크 GL% | 8.7% | **14.2%** |

## 주의

- pseudo-mask 사용 **안 함**
- `*.pt` git 미추적 (meta만 커밋)
