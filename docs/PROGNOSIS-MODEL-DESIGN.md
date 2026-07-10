# 시계열 예후 예측 모델 설계 (Prognosis Model)

> IRB: 국내 임상기관 승인 (2019) · 로컬 전용  
> 최종 업데이트: **2026-07-09** · **Phase 1 보류** · GL 추이 분석으로 대체  
> 관련: `docs/PROGNOSIS-TRACKING-DESIGN.md` · `timeseries_analysis_summary.json`

---

## §1 목적

단순 **「현재 시점 진단」**을 넘어 **「이 환자는 향후 N개월 후 어떻게 변할 것인가」**를 예측합니다.

| 임상 활용 | 설명 |
|:---|:---|
| 치료 강도 조정 | progression 고위험 → 약물/수술 강화 검토 |
| 추적 간격 결정 | 저위험 → follow-up 연장, 고위험 → 단축 |
| audit 연동 | AI 예측 vs 실제 결과 비교 → 신뢰도 누적 |

---

## §2 데이터 현황 (STEP 0 실측, 2026-07-09)

GPU `analyze_timeseries_labels.py` 실행 결과 (`timeseries_analysis_summary.json`):

| 항목 | 실측값 | 비고 |
|:---|:---|:---|
| 총 환자 | **173명** | |
| 복수 방문 | **92명** | 예상 60명 초과 |
| 인접 방문 쌍 | **113쌍** | Phase 1 후보 |
| 방문 간격 | **평균 204일** | 최소 4일 · 최대 854일 |
| 안저+시야검사 동시 | **167명** | |

**Grade 변화 (113쌍)**:

| 변화 | 쌍 수 | 비율 |
|:---|:---|:---|
| stable | 108 | 95.6% |
| **progression** | **3** | **2.7%** |
| improvement | 2 | 1.8% |

### Phase 1 보류 결정 (2026-07-09)

**progression=3쌍**으로 MLP 5-fold CV 불가:

- fold당 progression 0~1개 → AUC 불안정
- 항상 stable 예측 시 정확도 95.6% → **의미 없는 모델**
- **데이터 품질 문제가 아님** — Grade 변화는 임상에서 **수년에 걸쳐 서서히** 진행

**단기 대안**: `scripts/analyze_gl_trend.py` — v15 GL 확률 **방문 간 변화(Δprob)** 분석

**중기**: `gl_visit_snapshots` DB 축적 → progression ≥50쌍 후 Phase 2

---

## §3 모델 아키텍처 (3단계)

### Phase 1 (구현 완료 · **훈련 보류**): 이진 예후 MLP

코드: `build_prognosis_pairs.py` · `train_prognosis_mlp.py` · `eval_prognosis.py`  
상태: **progression 부족으로 실행 중단** — 코드는 Phase 2 재개용 보존

### Phase 2 (progression ≥50쌍): 시계열 모델

- 조건: progression 사례 **≥50쌍** (현재 3 → 목표 대비 **~17배**)
- 병원협력(SaMD LOI) 통한 데이터 확대 필요
- 모델: LSTM / Transformer

### Phase 3 (병원 협력): 멀티모달 시계열

- 안저 + VF MD/PSD + OCT RNFL/CDR + 인구통계
- 1년/2년 Grade · 실명 위험도

---

## §4 Phase 1 설계 (참고 — 보류)

인접 방문 쌍 + v14/v15 backbone freeze + MLP.  
113쌍 중 progression 3쌍 → **통계적으로 학습 불가**.

---

## §5 구현 · 실행

| 파일 | 상태 |
|:---|:---|
| `scripts/analyze_timeseries_labels.py` | ✅ STEP 0 |
| `scripts/build_prognosis_pairs.py` | ✅ (113쌍 생성 가능) |
| `scripts/train_prognosis_mlp.py` | ⏸️ 보류 |
| `scripts/analyze_gl_trend.py` | ✅ **현재 실행 대상** |
| `scripts/run_prognosis_gpu.sh` | Phase 1 파이프라인 (보류) |

**GL 추이 분석 (GPU)**:

```bash
python3 scripts/export_v15_onnx.py --checkpoint models/retinal_v15/best.pt --output models/retinal_v15.onnx
python3 scripts/analyze_gl_trend.py
# → gl_trend_analysis.json
```

---

## §6 medi-audit-engine 연동

지금부터 모든 방문을 `gl_visit_snapshots`에 기록 → 1~2년 후 progression 50+ 확보 시 Phase 2.

---

## §7 성공 기준 (재설정)

| 단계 | 기준 | 상태 |
|:---|:---|:---|
| Phase 1 MLP | AUC ≥0.65 · progression ≥50쌍 | ⏸️ **보류** (3쌍) |
| **GL 추이 분석** | Δprob vs Grade 상관 · 상승 ≥0.1 환자 비율 | 🔄 실행 대상 |
| Phase 2 | progression ≥50쌍 + LOI 데이터 | ⏳ 대기 |

---

## 로드맵

```
[현재]  GL 확률 추이 분석 (analyze_gl_trend.py)
[보류]  Phase 1 MLP (progression=3)
[Phase2] progression≥50 → LSTM/Transformer (병원협력)
[Phase3] Cross-modal 1y/2y 예측
```
