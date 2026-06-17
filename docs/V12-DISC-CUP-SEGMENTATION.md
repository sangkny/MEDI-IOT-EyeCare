# v12 Disc/Cup 보조 세그멘테이션 헤드

## 1. 배경 (최신 연구 동향)

2025–2026 GL 특화 연구(SwinCup-DiscNet 등)의 공통 트렌드:

1. **Disc/Cup 세그멘테이션**으로 시신경 유두 구조를 명시적으로 모델링
2. 세그 결과에서 **CDR(Cup-to-Disc Ratio)** 를 계산
3. CDR 또는 세그 특징을 **분류 헤드**와 결합

순수 백본 교체(EfficientNet→ConvNeXt/Swin)보다 **보조 태스크 추가**가 더 일관된 개선 방향으로 보고됨.

v12는 v10c와 동일 **EfficientNet-B4** 백본을 유지하고, G1020 disc/cup 폴리곤 라벨로 **보조 세그 헤드**를 추가한다.

## 2. 데이터

| 항목 | 내용 |
|------|------|
| 소스 | G1020 `Images/*.json` (labelme: disc, cup, discLoc) |
| 마스크 | `disc_cup_masks/G1020/{imageID}_mask.png` |
| 픽셀 값 | 0=배경, 1=disc, 2=cup |
| 전처리 | CenterCrop(짧은 변) → 224×224, **INTER_NEAREST** |
| manifest | `unified_v12.json` — `disc_cup_mask` 필드 (없으면 `null`) |

생성 스크립트:

```bash
# GPU Docker 내부
python3 /workspace/scripts/build_disc_cup_masks.py
python3 /workspace/scripts/build_v12_manifest.py
```

## 3. 모델 구조

```
EfficientNet-B4 features
    ├─ avgpool → 5개 분류 헤드 (dr, glaucoma, amd, myopia, multidisease)
    └─ seg_head → (N, 3, 224, 224)  [배경/disc/cup]
```

- v10c 5-head는 **변경 없음**
- `seg_head`: Conv1×1 → Upsample → Conv1×1 (3-class)
- 1차: GL 헤드에 CDR concat 없이 **multi-task loss**만 적용

## 4. CDR 계산 로직

`services/cdr_estimator.py`:

- `cdr_from_disc_cup_mask(mask)` — 픽셀 마스크에서 cup_area / disc_area
- `cdr_from_seg_logits(logits)` — argmax 세그 → 동일 공식

```python
cup_area = (pred == 2).sum()
disc_area = ((pred == 1) | (pred == 2)).sum()
cdr = cup_area / max(disc_area, 1)
```

## 5. 훈련

| 항목 | 값 |
|------|-----|
| manifest | `unified_v12.json` |
| loss 가중치 | dr=0.25 gl=0.28 amd=0.17 myo=0.17 multi=0.13 **seg=0.05** |
| seg loss | CrossEntropyLoss(ignore_index=-1) — 마스크 없는 샘플 제외 |
| composite | 기존 5-task ×0.95 + seg_dice ×0.05 |
| 실행 | `V12=1 bash scripts/start_v10_train.sh` |
| smoke | `python3 training/train_v10.py --manifest unified_v12.json --smoke --seg-head --epochs 1` |

## 6. 훈련 결과

> 완료 후 채움 (v10c baseline: composite **0.8842**, GL **0.835**)

| 지표 | v10c | v12 |
|------|------|-----|
| composite | 0.8842 | TBD |
| GL AUC | 0.835 | TBD |
| seg_dice | — | TBD |

## 7. v10c 대비

| 구분 | v10d/e/f | v12 |
|------|----------|-----|
| 변경 유형 | 입력/전처리/데이터만 | **구조 변경** (보조 seg head) |
| 백본 | EfficientNet-B4 | 동일 |
| GL 개선 가설 | 데이터·전처리 | Disc/Cup 구조적 prior |
