# V15 Grade Head 훈련 계획

> 최종 업데이트: **2026-07-11** · **v15b 수정크롭 재훈련 완료**

## §1 목적

v14는 한국인 NTG 검출(mean_prob **0.842**, detection **1.000**)에 성공했으나 Grade 변별력이 부족하다. v15는 `glaucoma_grade` 보조 헤드를 추가한다. **v15b**는 disc_peak_v2 수정 크롭으로 재전처리·재훈련한 운영 버전이다.

## §2 v14 문제점 분석

| 원인 | 설명 |
|:---|:---|
| 이진 GL만 학습 | `gl_head` sigmoid — 녹내장 여부만 학습, Grade 미학습 |
| oversample 한계 | `gl_oversample=2.0`은 GL 샘플 비중만 높임 |
| severity AUC 하락 | v10c 0.677 → v14 0.602 (Grade 1/2/3 logits 없음) |

## §3 grade_head 설계

```python
self.grade_head = nn.Linear(feat_dim, 4)  # 0=정상, 1=경증, 2=중등도, 3=중증
```

| 항목 | 값 |
|:---|:---|
| Loss | CrossEntropy (masked) |
| `GRADE_LOSS_WEIGHT` | **0.05** (보조 태스크) |
| `GRADE_COMPOSITE_WEIGHT` | **0.05** |
| mask | `korean_clinical` + grade ∈ {1,2,3} 만 loss 적용 |
| 메인 태스크 | `gl_head` 이진 (유지) |

composite: 기존 5-head + `gradeQWK × 0.05`

## §4 데이터 구성 (`unified_v15.json`)

`build_v15_manifest.py` — `unified_v14.json` 기반:

| 출처 | glaucoma_grade | mask_grade (loss) |
|:---|:---|:---|
| 한국인 임상 | 1 / 2 / 3 (실제) | ✅ |
| 공개 GL 음성 | 0 | ❌ |
| 공개 GL 양성 | 1 (근사) | ❌ |

**v15b**: 한국인 크롭 = `disc_peak_v2` 재전처리 (2026-07-10) 후 동일 manifest 경로로 재훈련.

## §5 훈련 설정

```bash
V15=1 bash scripts/start_v10_train.sh
```

| 파라미터 | 값 |
|:---|:---|
| manifest | `training/manifests/unified_v15.json` |
| output | `models/retinal_v15` |
| pretrained | `models/retinal_v14/best.pt` |
| DR / GL / AMD / MYO / MULTI | 0.28 / **0.25** / 0.17 / 0.17 / 0.08 |
| grade_weight | **0.05** |
| gl_oversample | **2.0** |
| warmup_epochs | 8 |

## §6 실측 결과

### v15 (이전 크롭, 2026-07-09)

| 지표 | 값 |
|:---|:---|
| composite | 0.803 |
| GL AUC | 0.832 |
| gradeQWK | 0.551 |
| AUC(severity) | 0.652 |

### v15b (수정 크롭, 2026-07-11) ✅

| 지표 | 값 |
|:---|:---|
| best_composite | **0.8110** (epoch 45/49/55) |
| early_stop | epoch **57** |
| gradeQWK | **0.600** |
| GL AUC (공개) | **0.840** |
| NTG mean_prob | **0.842** (v14 수준 회복) |
| detection@0.5 | 0.997 |
| AUC(severity) | 0.606 |

**크롭 수정 효과**: gradeQWK **+0.049** · GL AUC **+0.008** · composite **+0.008**

> **AUC(severity)**: binary GL 확률↔Grade 상관. Grade 변별 SSOT는 **gradeQWK**.

eval: `python3 scripts/eval_korean_gl.py --model models/retinal_v15/best.pt`  
export: `python3 scripts/export_v15_onnx.py` · 수정본 `scripts/export_v15_onnx_fix.py`

## §7 운영 전략 (2026-07-11 확정)

| 용도 | 모델 |
|:---|:---|
| 일반 스크리닝 | **v10c** |
| 한국인 NTG 검출 | **v14** |
| Grade 변별 | **v15b** |
| 정밀 앙상블 | **v10c + glaucoma_v2** |
