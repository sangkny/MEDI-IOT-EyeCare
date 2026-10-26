# 증례 대시보드

기존 EYECARE FastAPI 앱의 `/api/v1/clinical-support`에 붙인다. 별도 시연 앱이 아니다. 화면은 `static/clinical-dashboard/index.html`이고 집계 API를 호출한다.

## 진행 기록

### 2026-10-27T00:16:54+09:00 — 게시

- TASK_ID: PC2-EYECARE-DASHBOARD-010-PUBLICATION-005
- CODE_COMMIT: bf95fc5a327653a710adbd328e3b12a52cd6a784
- START_TIME_KST: 2026-10-27T00:16:54+09:00
- END_TIME_KST: 2026-10-27T00:19:49+09:00
- ELAPSED: PT2M55S
- STATUS: DASHBOARD010_PUBLISHED
- 상세: `CLINICAL-DASHBOARD-SPEC.md`

### 2026-10-26T20:40:41+09:00 — 전체 앱에서 확인

- TASK_ID: PC2-EYECARE-DASHBOARD-010-FULL-RUNTIME-FIX-004
- START_TIME_KST: 2026-10-26T20:40:41+09:00
- END_TIME_KST: 2026-10-26T20:50:46+09:00
- ELAPSED: PT10M5S
- STATUS: FULL_EYECARE_DASHBOARD_VERIFIED
- URL: `http://127.0.0.1:8001/clinical-dashboard`
- 상세: `CLINICAL-DASHBOARD-SPEC.md`

### 2026-10-26T19:35:01+09:00 — 런타임 검증

- TASK_ID: PC2-EYECARE-DASHBOARD-010-RUNTIME-VALIDATION-002
- EXECUTION_HOST: SVG-SKLEE (PC2)
- BRANCH: feat/clinical-case-dashboard-010
- HEAD: 600ac7bd6f3dca5b7ef8cc998c621b43828a5f16
- START_TIME_KST: 2026-10-26T19:35:01+09:00
- END_TIME_KST: 2026-10-26T19:48:09+09:00
- ELAPSED: PT13M8S
- STATUS: PARTIALLY_VERIFIED
- 상세: `CLINICAL-DASHBOARD-SPEC.md`, `CLINICAL-VISUAL-ANALYTICS-SPEC.md`
- 전체 `import main`은 기존 운영 대시보드가 `anthropic` 패키지를 불러오다 실패한다. 증례 화면은 그 임포트 전에 등록되지 않는다
- 격리 서버 `http://127.0.0.1:8766/clinical-dashboard`는 HTML 200이었다. 데이터 API는 JSON이다
- 커밋과 푸시 없음

### 2026-10-26T18:10:06+09:00 — Phase 010 착수

- TASK_ID: PC2-EYECARE-PHASE010-START-UPDATE
- EXECUTION_HOST: SVG-SKLEE (PC2)
- BRANCH: feat/clinical-case-dashboard-010
- BASE_BRANCH: feat/clinical-protocol-validation-009
- BASE_HEAD: 600ac7bd6f3dca5b7ef8cc998c621b43828a5f16
- START_TIME_KST: 2026-10-26T18:10:06+09:00
- END_TIME_KST: 2026-10-26T18:15:01+09:00
- ELAPSED: PT4M55S
- SPEC_FILE: `PC2-EYECARE-CLINICAL-DASHBOARD-010` 파일은 저장소와 로컬 문서에서 찾지 못했다. 이번 작업 요구를 구현 기준으로 사용했다
- TEST_RESULTS: `tests/test_clinical_case_dashboard.py` 2 passed, exit 0. `tests/test_clinical_import.py` 15 passed, 1 skipped, exit 0. 브라우저 조작 검증은 하지 않음
- SAFETY: `enable_r1` false, `protocol_advisory_id` 없음, `window_check` false, 미승인 규칙 ACTIVE 아님, 자동 수정·확정·잠금 없음, 배정 값은 조회하지 않음
- NEXT_APPROVAL: 커밋과 푸시 없음. main과 PC1은 변경하지 않음

## 화면

연구 개요, 대상자, 방문, TBUT/OSDI/Schirmer 상자 그림과 경과 선, 결측 칸 수, 품질·질의 건수, 가져오기 대조를 한 화면에 둔다. 토큰과 연구·사이트 ID가 있어야 집계가 채워진다. 이전 반출 집계 숫자는 화면에 넣지 않는다.

초안과 확정은 따로 센다. 확정 기술통계와 초안 탐색 그림은 같은 상자에 넣지 않는다. 초안 그림에는 DRAFT / NON-FINAL 제목을 붙이고 효과 판정을 쓰지 않는다. 대상자를 고르기 전에는 측정값을 내려 주지 않는다. 스테이징과 미해결 가져오기 행은 개수만 보여 주고 원본 칸은 반환하지 않는다.

## 안전

사이트 구성원이 아니면 조회가 거절된다. 단위는 관찰에 있으면 그 값을, 없으면 계획서 메타데이터로 표시하고 `unit_origin`으로 구분한다. 반출 검증 API는 파일을 저장하지 않고 집계만 반환한다. DeeVo에는 접속하지 않는다.
