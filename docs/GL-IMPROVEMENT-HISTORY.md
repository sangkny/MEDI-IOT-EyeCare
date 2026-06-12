# GL AUC 개선 이력

fast mode GL AUC 목표: **0.900+** (v10c baseline 0.835)

| 버전 | GL AUC | composite | 방법 | 날짜 |
|------|--------|-----------|------|------|
| v10 | 0.804 | 0.8818 | gl_w=0.20 | 2026-06-08 |
| v10b | 0.841 | 0.8726 | gl_w=0.35 | 2026-06-09 |
| v10c | 0.835 | 0.8842 | gl_w=0.28 | 2026-06-10 |
| v10c+ensemble | TBD | 0.8842 | v10c+glaucoma_v2 앙상블 (0.30~0.70) | 2026-06-12 |
| v10d | TBD | TBD | gl_w=0.32 + GL 증강 + oversample 1.5 | 예정 |

## 앙상블 (Part D)

- 불확실 구간: v10c GL prob **0.30 ~ 0.70**
- 가중치: v10c **0.35** / glaucoma_v2 **0.65**
- 환경변수: `MEDI_GL_ENSEMBLE_ENABLED=1` (기본 on)

측정:

```bash
python scripts/measure_gl_auc.py --manifest training/manifests/unified_v10.json
```

## v10d 훈련 (Part B)

```bash
V10D=1 bash scripts/start_v10_train.sh
```

- `GL_WEIGHT=0.32`, `GL_OVERSAMPLE=1.5`
- GL 전용 증강: RandomRotation(20°), RandomAffine, RandomAutocontrast
