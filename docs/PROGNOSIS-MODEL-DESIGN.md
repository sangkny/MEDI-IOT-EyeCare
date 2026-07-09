# 시계열 예후 예측 모델 설계 (Prognosis Model)

> IRB: 국내 임상기관 승인 (2019) · 로컬 전용  
> 최종 업데이트: 2026-07-09 · Phase 1 구현 착수  
> 관련: `docs/PROGNOSIS-TRACKING-DESIGN.md` (DB/audit) · `services/prognosis_tracker.py`

---

## §1 목적

단순 **「현재 시점 진단」**을 넘어 **「이 환자는 향후 N개월 후 어떻게 변할 것인가」**를 예측합니다.

| 임상 활용 | 설명 |
|:---|:---|
| 치료 강도 조정 | progression 고위험 → 약물/수술 강화 검토 |
| 추적 간격 결정 | 저위험 → follow-up 연장, 고위험 → 단축 |
| audit 연동 | AI 예측 vs 실제 결과 비교 → 신뢰도 누적 |

---

## §2 데이터 현황 (STEP 0)

**배경 통계** (전처리·`build_timeseries_labels.py` 기준):

| 항목 | 값 |
|:---|:---|
| 복수 방문 환자 | **~60명** |
| 평균 방문 간격 | **~229일** (~7.6개월) |
| 안저사진 (origin) | 399장 |
| 시야검사 | 292장 |
| OCT | 172장 |
| 모달리티 | 안저 + 시야검사(선택) + OCT(선택) |

**실측 확인** (GPU):

```bash
python3 scripts/analyze_timeseries_labels.py
# 또는
bash scripts/run_prognosis_gpu.sh  # STEP 0 포함
```

출력: 방문 횟수 분포, Grade 변화(progression/stable/improvement), 인접 방문 쌍 수, 안저+VF 동시 보유 환자 수.

**Phase 1 학습 쌍**: 복수방문 환자의 **인접 방문 쌍**만 사용 → 예상 **~78쌍** (60명 × 평균 1.3쌍).

---

## §3 모델 아키텍처 (3단계)

### Phase 1 (현재 구현): 이진 예후 예측

| 항목 | 내용 |
|:---|:---|
| 입력 | 현재 방문 안저(OD+OS) + Grade + NTG + 방문 간격 |
| 출력 | 다음 방문까지 **악화(progression=1)** vs 유지/호전(0) |
| 모델 | v14/v15 CNN backbone (freeze) → **MLP** |
| 데이터 | ~78 인접 방문 쌍 |

**장점**: 소규모 데이터로 즉시 시작 가능  
**한계**: 시계열 순서·다중 방문 문맥 미활용

### Phase 2 (데이터 100쌍+): 시계열 모델

- 입력: 방문 시퀀스 `[visit_1, …, visit_N]` — 각 visit = (안저 임베딩, VF 수치, OCT CDR, 일수)
- 출력: 다음 Grade, 악화 확률
- 모델: LSTM 또는 Transformer (temporal attention)

### Phase 3 (병원 협력 후): 멀티모달 시계열

- 입력: 안저 + VF MD/PSD + OCT RNFL/CDR + 인구통계
- 출력: 1년/2년 후 Grade, 실명 위험도
- 모델: Cross-modal Transformer

---

## §4 Phase 1 구체 설계

### 데이터 준비 (`build_prognosis_pairs.py`)

```
visit_i (OD, OS fundus) + grade_i, is_ntg, days_interval
  → label: grade_change == 'progression' ? 1 : 0
```

| 컬럼 | 설명 |
|:---|:---|
| `fundus_R_i`, `fundus_L_i` | 방문 i 안저 파일명 |
| `path_fundus_*` | `origin/fundus/OD|OS/` 절대 경로 |
| `label` | progression=1, stable/improvement=0 |

분할: **5-fold StratifiedKFold** (train 스크립트 내) — 소규모이므로 고정 hold-out 대신 CV.

### 특징 추출 (v14/v15 backbone)

```
features(x) → avgpool → 1792-d
OD_emb + OS_emb → 3584-d
+ grade/3, is_ntg, days/365 → 3587-d
```

v15 훈련 완료 후 `--backbone models/retinal_v15/best.pt`로 교체만 하면 됨.

### MLP 분류기

```
Linear(3587→512) → ReLU → Dropout(0.3)
Linear(512→128)  → ReLU → Dropout(0.3)
Linear(128→1)    → Sigmoid
Loss: BCEWithLogits + pos_weight (progression 소수 클래스 up-weight)
```

### 한계 (명시)

- **N≈78쌍** → 과적합 위험 높음
- Dropout·L2·5-fold CV 필수
- 결과는 **탐색적(exploratory)** 수준으로만 해석
- 외부 검증셋·전향 연구 전까지 임상 의사결정 단독 사용 금지

---

## §5 구현 계획

| 파일 | 역할 |
|:---|:---|
| `scripts/analyze_timeseries_labels.py` | STEP 0 실측 분석 |
| `scripts/build_prognosis_pairs.py` | `prognosis_pairs.csv` 생성 |
| `scripts/train_prognosis_mlp.py` | 5-fold MLP CV, `models/prognosis_v1/best.pt` |
| `scripts/eval_prognosis.py` | AUC·민감도·특이도 + 환자별 확률 |
| `scripts/run_prognosis_gpu.sh` | Docker 일괄 실행 |
| `services/prognosis_tracker.py` | `predict_progression()` API |

**실행**:

```bash
bash scripts/run_prognosis_gpu.sh
# smoke: SMOKE=1 bash scripts/run_prognosis_gpu.sh
```

---

## §6 medi-audit-engine 연동 계획

예후 예측 결과를 `gl_prognosis_events`에 자동 기록:

```
event: "AI 예측: 6개월 후 progression 확률 72% (risk=high)"
```

임상의가 실제 follow-up 결과 입력 → 예측 vs 실제 비교 → 모델 calibration 누적 (향후 Phase 2+).

DB 스키마: `PrognosisTracker.get_schema_sql()` · `PROGNOSIS-TRACKING-DESIGN.md`

---

## §7 성공 기준 (Phase 1)

| 지표 | 목표 | 비고 |
|:---|:---|:---|
| ROC AUC | **≥ 0.65** | 랜덤 0.5 대비 유의 개선 |
| 민감도 | **≥ 0.60** | 악화 환자 놓침 최소화 우선 |
| 5-fold CV | 일관성 | fold 간 AUC 편차 모니터링 |

**v15 병행**: v15 훈련 중 → backbone은 **v14** 사용, 완료 후 v15로 교체.

---

## 로드맵 요약

```
Phase 1 (지금)  MLP + 인접 쌍 ~78   → progression 이진
Phase 2 (100쌍+) LSTM/Transformer  → Grade 시계열
Phase 3 (협력)   Cross-modal        → 1y/2y Grade + 실명 위험
```
