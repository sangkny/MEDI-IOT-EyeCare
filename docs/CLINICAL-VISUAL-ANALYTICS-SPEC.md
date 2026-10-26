# 증례 시각화 입력 규칙

상자 그림과 개인 추이는 저장된 `value_number`만 쓴다. 대시보드는 OSDI를 다시 계산하지 않고, TBUT 반복값을 평균으로 바꾸지 않으며, 관찰 행을 수정하지 않는다.

## 진행 기록

### 2026-10-27T00:16:54+09:00 — 게시 확인

- CODE_COMMIT: bf95fc5a327653a710adbd328e3b12a52cd6a784
- 합성 `SYN-01` 재조회에서 FINAL은 SCHIRMER와 TBUT, DRAFT는 OSDI_SCORE와 TBUT였다. 두 인구를 한 상자에 넣지 않았다

### 2026-10-26T20:40:41+09:00 — 전체 앱 화면에서 재확인

- 합성 대상자 `SYN-01`의 V1은 TBUT, OSDI_SCORE, SCHIRMER가 없고 V2는 값이 있다
- FINAL은 Schirmer OS `standard`와 TBUT OD `reported_average`다
- DRAFT / NON-FINAL은 OSDI_SCORE와 TBUT OD `repeat`다
- 배정 값은 응답과 화면에 없다

### 2026-10-26T19:35:01+09:00 — 런타임 검증에서 확정

- TASK_ID: PC2-EYECARE-DASHBOARD-010-RUNTIME-VALIDATION-002
- HEAD: 600ac7bd6f3dca5b7ef8cc998c621b43828a5f16
- 초안과 확정은 `final_descriptive`와 `draft_exploratory`로 나눈다. 한 상자에 섞지 않는다
- 초안 그림의 제목은 DRAFT / NON-FINAL이다. 효과 문장은 넣지 않는다
- 확정 숫자가 없으면 그 인구의 상자 목록은 비어 있다
- 눈(`laterality`)과 방법(`method`)이 다르면 다른 상자다. TBUT `repeat`와 `reported_average`를 한 분위에 넣지 않는다
- OSDI는 저장된 `OSDI_SCORE`만 표시하고 `recalculated`는 false다
- Schirmer 단위는 관찰 단위가 있으면 그 값, 없으면 `mm/5min`이다. `unit_origin`으로 구분한다
- 숫자가 없고 문자가 있는 값은 비숫자 건수로 센다. 결측 분모의 `absent`와 구분한다
- 방문 순서는 V1, V2, V3, V4, V5, V6이다
- 계획서 메타데이터에서 V5의 OSDI 기대값은 거짓이고 V6은 참이다. 방문 창은 계산하지 않는다
- 같은 대상자·방문의 여러 관찰은 `repeat_index`를 유지한다
- 결측 표의 `expected`가 분모다. 확정 숫자, 초안 숫자, 비숫자, 없음을 따로 센다
- 출처 표는 대상자를 선택한 뒤에만 채운다. 값과 배정 코드는 출처 표에 넣지 않는다
- 사이트 집계 응답에는 개인 측정 배열을 넣지 않는다

브라우저에서 합성 V1·V2의 FINAL 상자와 DRAFT 상자, 결측 표, 출처 표를 봤다. V5·V6 분모는 합성 테스트 `test_subject_series_keeps_draft_final_eyes_and_hides_allocation`에서 확인했다.
