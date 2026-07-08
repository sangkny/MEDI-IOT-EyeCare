# V15 Grade Head 훈련 계획

> 최종 업데이트: 2026-07-09 · v14 완료(7e69dbd) 후 Grade 변별력 개선

## §1 목적

v14는 한국인 NTG 검출(mean_prob **0.842**, detection **1.000**)에 성공했으나 **AUC(severity)=0.602**로 Grade 1/2/3 변별력이 부족하다. v15는 `glaucoma_grade` 보조 헤드를 추가해 중증도 변별력을 개선한다.

**목표**: AUC(severity) **0.602 → 0.700+** (한국인 eval 기준)

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

사전 준비:

```bash
bash scripts/run_build_v15_manifest_gpu.sh
bash scripts/run_v15_smoke_gpu.sh   # device=cuda + gradeQWK 로그 확인
```

## §6 성공 기준

| 지표 | v14 | v15 목표 |
|:---|:---|:---|
| GL AUC (공개) | 0.842 | **≥ 0.842** (유지) |
| NTG mean_prob | 0.842 | **≥ 0.800** |
| AUC(severity) | 0.602 | **≥ 0.700** |
| gradeQWK (val) | — | > 0 (smoke+) |

eval: `python3 scripts/eval_korean_gl.py --model models/retinal_v15/best.pt`

## §7 배포 전략 (예정)

- 한국인 + severity 필요 → **v15**
- 한국인 검출만 → v14 유지
- 일반 → v10c
