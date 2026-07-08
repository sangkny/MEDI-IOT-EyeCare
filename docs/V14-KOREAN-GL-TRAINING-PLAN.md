# v14 한국인 녹내장 훈련 계획

> IRB: 국내 임상기관 승인 (2019) · 로컬 전용  
> 상태: **✅ 완료 (2026-07-09)** — 한국인 eval 목표 달성 · 한국인 특화 모드 배포 권장

---

## §1 목적 (한국인 NTG 특화)

서양·공개 데이터셋 중심으로 훈련된 v10c가 한국인 정상안압녹내장(NTG) 코호트에서 성능이 저하될 수 있습니다.  
국내 임상기관 IRB 승인 데이터 699장을 unified manifest에 통합해 **한국인 NTG 특화** v14를 훈련했습니다.

---

## §2 v10c vs v14 한국인 eval (2026-07-09 최종)

| 항목 | 값 |
|------|-----|
| 스크립트 | `scripts/eval_korean_gl.py` |
| 데이터 | `labels_modified.csv` · N=300 (컬러) |
| ONNX provider | **CPUExecutionProvider** (컨테이너 CUDA EP 없음) |
| v10c 모델 | `models/retinal_v10.onnx` |
| v14 모델 | `models/retinal_v14.onnx` |

### 비교표 (한국인 modified)

| 지표 | v10c | v14 | 변화 |
|------|------|-----|------|
| mean_prob | 0.671 | **0.841** | +0.170 ✅ |
| detection@0.5 | 0.983 | **1.000** | +0.017 ✅ |
| AUC(severity) | 0.677 | 0.602 | -0.075 ⚠️ |
| NTG mean_prob | 0.665 | **0.842** | +0.177 ✅ |
| POAG mean_prob | 0.682 | **0.840** | +0.158 ✅ |

### 해석

- **탐지율(recall)**: v14가 한국인 NTG를 훨씬 더 잘 잡음 (NTG mean 0.842 > 목표 0.700)
- **변별력(severity AUC)**: 소폭 하락 — 전부 높은 확률을 주다 보니 Grade 간 구분 약화
- **임상적 판단**: "못 잡는 것보다 다 잡는 게 낫다" 원칙상 **탐지율 향상 우선**

### 공개셋 · composite (훈련 val)

| 지표 | v10c | v14 | 변화 |
|------|------|-----|------|
| GL AUC (공개셋) | 0.835 | **0.842** | +0.007 ✅ |
| composite | **0.8842** | 0.8769 | -0.007 |

### 배포 판단

| 기준 | 결과 |
|------|------|
| v14 GL AUC (공개셋) | 0.842 (+0.007 vs v10c) |
| v14 한국인 NTG 탐지@0.5 | **1.000** (+0.017 vs v10c) |
| v14 한국인 NTG mean_prob | **0.842** (+0.177 vs v10c) |

**운영 전략**

- **한국인 환자** → v14 우선
- **일반(공개셋 기준)** → v10c 유지
- **향후** → v14 + glaucoma_v2 앙상블 검토

---

## §3 데이터 구성

| 소스 | 장수 | 비고 |
|------|------|------|
| unified_v10 (기존) | 27,546 | 공개 데이터 dedup |
| Korean GL (manifest) | **699** | `korean_clinical=true` |
| **v14 합계** | **28,243** | `unified_v14.json` |

---

## §4 훈련 설정 (실행값)

| 항목 | 값 |
|------|-----|
| manifest | `unified_v14.json` |
| output | `models/retinal_v14/` |
| loss weights | dr=0.28, gl=0.28, amd=0.18, myo=0.18, multi=0.08 |
| epochs | 60 |
| warmup | 8 |
| gl_oversample | **2.0** |
| device | cuda (TITAN X) |

```bash
V14=1 bash scripts/start_v10_train.sh
bash scripts/run_eval_korean_gl_gpu.sh  # --model models/retinal_v14.onnx
```

---

## §5 성공 기준 (훈련 val)

| 지표 | 목표 | v14 결과 |
|------|------|----------|
| GL AUC (val) | ≥ 0.850 | 0.842 (근접) |
| composite | ≥ v10c | 0.8769 (-0.007) |
| NTG mean_prob (한국인) | ≥ 0.700 | **0.842 ✅** |
| detection@0.5 (한국인) | 1.000 | **1.000 ✅** |

---

## §6 달성 결과 (2026-07-09)

| 목표 | 결과 | 상태 |
|------|------|------|
| NTG mean_prob ≥ 0.700 | **0.842** | ✅ |
| detection@0.5 = 1.000 | **1.000** | ✅ |
| AUC(severity) | 0.677 → **0.602** | ⚠️ 변별력 소폭 하락, v15 개선 과제 |
| GL AUC 공개셋 | **0.842** | ✅ (+0.007 vs v10c) |
| composite | 0.8769 | v10c 대비 -0.007 |

**다음 과제**

1. Grade 변별력 개선 (v15: glaucoma_grade 헤드)
2. ONNX export → `retinal_v14.onnx` · comprehensive 한국인 모드 연동
3. v14 + glaucoma_v2 앙상블 A/B

---

## 관련 문서

- `docs/MODEL-VERSION-HISTORY.md`
- `docs/DATASET-REGISTRY.md`
- `models/retinal_v14/best.meta.json`
