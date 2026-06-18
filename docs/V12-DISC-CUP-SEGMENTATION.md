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
| **커버리지** | 1,020 / 27,546 (**3.7%**) · GL 중 **8.7%** |

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
- `seg_head`: Conv1×1(256) → Conv1×1(3) → Upsample — **Conv를 7×7에서 먼저** 적용해 메모리 절감
- 1차: GL 헤드에 CDR concat 없이 **multi-task loss**만 적용

## 4. CDR 계산 로직

`services/cdr_estimator.py`:

- `cdr_from_disc_cup_mask(mask)` — 픽셀 마스크에서 cup_area / disc_area
- `cdr_from_seg_logits(logits)` — argmax 세그 → 동일 공식

## 5. 훈련 설정

| 항목 | 값 |
|------|-----|
| manifest | `unified_v12.json` |
| loss 가중치 | dr=0.25 gl=0.28 amd=0.17 myo=0.17 multi=0.13 **seg=0.05** |
| seg loss | CrossEntropyLoss(ignore_index=-1) |
| composite | 기존 5-task ×0.95 + seg_dice ×0.05 |
| 실행 | `V12=1 bash scripts/start_v10_train.sh` |

### 메모리 (해결됨)

Conv(3ch) 먼저 → Upsample 마지막. 본 훈련 peak **7.69GB**.

## 6. 훈련 결과 (2026-06-19)

| 지표 | v10c | v12 | Δ |
|------|------|-----|---|
| composite | **0.8842** | 0.8719 | −0.0123 |
| GL AUC | **0.835** | ~0.829 | −0.006 |
| seg_dice | — | **0.978** | seg_head 완벽 학습 |
| GPU peak mem | — | **7.69GB** | 안전 |

**판정**: ❌ **미배포** — v10c 대비 composite·GL 모두 하락.

### 실패 원인

- segDice **0.978** → seg_head는 G1020 마스크에 대해 거의 완벽히 학습
- GL 미향상: 마스크 supervision **8.7%** (1,020 / 11,725 GL)
- backbone에 disc/cup prior 전달 **절대량·비율 부족**

### 다음 시도 (v13)

| 옵션 | 내용 |
|------|------|
| A | ORIGA Masks_Square(+651) → ~14.3% |
| B | RIM-ONE disc/cup 마스크 |
| **C** | **SAM pseudo-mask** → GL 11,725장 **~100%** ← 최우선 |

meta: `models/retinal_v12/best.meta.json`

## 7. v10c 대비

v12는 구조 변경(보조 seg)이나 **마스크 부족**으로 v10c 미달. v10e/e/f와 동일하게 **미배포**.
