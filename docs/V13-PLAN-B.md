# v13 Plan B — G1020 + ORIGA 실제 GT 마스크

## 배경

SAM/OSAM pseudo-mask 경로 실패 후 **실제 정답 마스크만** 사용.

| 소스 | 장수 | 경로 |
|------|------|------|
| G1020 GT | 1,020 | `disc_cup_masks/G1020/{stem}_mask.png` |
| ORIGA Masks_Square | 650 | `disc_cup_masks/ORIGA/{stem}_mask.png` |
| **합계** | **1,670** | GL 11,725 중 **~14.3%** |

## 실행 (GPU Docker)

```bash
bash scripts/run_build_v13_planb_gpu.sh
V13=1 bash scripts/start_v10_train.sh
# seg 가중치 조정: SEG_WEIGHT=0.02 V13=1 bash scripts/start_v10_train.sh
```

## manifest

- 입력: `unified_v12.json`
- 출력: `unified_v13.json` (`plan_b: true`)
- `disc_cup_mask_source`: `gt_g1020` | `gt_origa`

## 훈련 설정 (v13 Plan B)

| 항목 | 값 |
|------|-----|
| seg_weight | **0.05** (기본, `SEG_WEIGHT`로 override) |
| 성공 기준 | composite·GL **≥ v10c** (0.8842 / 0.835) |

## 주의

- pseudo-mask 사용 **안 함**
- ORIGA 원본: `Glaucoma_raw/ORIGA/Masks_Square/*.png` (0/1/2, 512² → CenterCrop → 224²)
