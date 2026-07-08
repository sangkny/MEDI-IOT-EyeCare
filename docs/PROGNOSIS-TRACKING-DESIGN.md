# 녹내장 예후 추적 설계 (Prognosis Tracking)

> IRB: 국내 임상기관 승인 (2019) · 로컬 전용  
> 구현 상태: **stub** (`services/prognosis_tracker.py`) — medi-audit-engine 연동 후 활성화

---

## §1 목적

녹내장은 만성 진행성 질환 — "지금 상태"보다 "어떻게 변해가는지"가 더 중요합니다.  
시계열 안저사진 + AI 추론 + 임상 측정값(시야검사/OCT)을 통합해 환자별 예후를 자동으로 추적하고 리포트를 생성합니다.

---

## §2 데이터 흐름

```
안저사진 (방문마다)
  ↓ v14 AI 추론
AI GL 확률 + CDR 예측
  ↓
gl_visit_snapshots (방문별 스냅샷 저장)
  ↓ compute_progression()
gl_prognosis_events (진행도 판정)
  ↓ generate_report()
리포트 (임상의 화면 / PDF / medi-audit-engine)
```

---

## §3 DB 테이블 (4개)

| 테이블 | 역할 |
|--------|------|
| `gl_patients` | 환자 엔티티 (`entity_type='glaucoma_patient'`) |
| `gl_visit_snapshots` | 방문별 측정값 + AI 추론값 |
| `gl_prognosis_events` | 예후 판정 이력 (append-only) |
| `gl_prognosis_reports` | 생성된 리포트 |

스키마 SQL: `PrognosisTracker.get_schema_sql()` 또는 `services/prognosis_tracker.py` 내 `PROGNOSIS_SCHEMA`

---

## §4 진행도 판정 기준

| 판정 | 기준 |
|------|------|
| `progression` | clinical_grade 증가 OR vf_md 악화(+1.0dB↑) OR OCT RNFL 감소(-5μm↓) |
| `stable` | 모든 지표 변화 없음 |
| `improvement` | grade 감소 (드묾, 치료 효과) |
| `flagged` | 단기간(90일 이내) Grade 2단계 이상 변화 |

---

## §5 medi-audit-engine 연동 계획

- `gl_prognosis_events` → `audit_events` 테이블과 동일한 append-only 패턴
- `entity_type='glaucoma_patient'` 로 `entities` 테이블 연동
- medi-audit-engine 구축 후 동일 DB로 통합

---

## §6 향후 AI 예후 예측 모델

| 항목 | 내용 |
|------|------|
| 입력 | `timeseries_labels.csv` (방문 시계열) |
| 모델 | LSTM or Transformer (방문 순서 → 다음 Grade 예측) |
| 출력 | 1년 후 Grade 악화 확률 |
| 규모 | 복수 방문 ~60명 · 평균 2.3회 방문 |

---

## §7 리포트 종류

| type | 용도 |
|------|------|
| `summary` | 환자용 요약 (Grade 변화 그래프, 전체 트렌드) |
| `clinical` | 임상의용 (시야검사/OCT 수치 포함) |
| `dsmb` | 임상시험용 데이터 안전모니터링 |

---

## 관련 파일

| 파일 | 설명 |
|------|------|
| `services/prognosis_tracker.py` | Stub 인터페이스 + SQL 스키마 |
| `scripts/build_timeseries_labels.py` | 시계열 라벨 CSV 생성 |
| `docs/V14-KOREAN-GL-TRAINING-PLAN.md` | v14 훈련 계획 |
