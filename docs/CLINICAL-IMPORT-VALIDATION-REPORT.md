# 외부 반출 검증 보고

식별자와 측정값은 포함하지 않는다. 원본 워크북은 수정하지 않았고 Git에 올리지 않는다.

## 진행 기록

### 2026-10-26T00:09:57+09:00 — 계획서 검증 게시

- TASK_ID: PC2-EYECARE-PROTOCOL009-PUBLICATION-003
- EXECUTION_HOST: SVG-SKLEE (PC2)
- BRANCH: feat/clinical-protocol-validation-009
- BASE_HEAD: 8fba4bfe59ccd28841653cfc55510852e1256ba3
- CODE_COMMIT: 85ef271b96e36a1a60508d66ff71ae37264235ca `feat: add advisory protocol validation for clinical imports`
- DOCS_COMMIT: 이 문서 커밋 `docs: record Sponsor Protocol v1.3 validation evidence`
- START_TIME_KST: 2026-10-26T00:09:57+09:00
- END_TIME_KST: 2026-10-26T00:10:50+09:00
- ELAPSED: PT53S
- STATUS: PROTOCOL009_PUBLISHED. 규칙은 EXTRACTED이며 기본 가져오기에서 꺼져 있다
- TEST_RESULTS: 이번 합성 SQLite 15 passed, 1 skipped, exit 0. pytest 종료 후 Python 프로세스는 없음. PostgreSQL은 이번 게시에서 다시 실행하지 않음. 이전 증거는 2026-10-25T23:41 기록의 일회용 PostgreSQL 15, `medi010_external_clinical_import`, 합성 1 passed, exit 0, 컨테이너 삭제
- PUSH: origin `feat/clinical-protocol-validation-009`만 일반 푸시
- REMAINING_ISSUES: 서명 승인, ±3일과 ±7일, 방문 6 OSDI 그림, 반올림 자릿수, 단위 문자만 있는 칸의 의미, 연구 귀속, R1 운영 승인, 반복 양식 원본 키
- NEXT_APPROVAL: 규칙 활성화, 운영 반입, 배포, PR 병합은 하지 않음. Phase 010은 시작하지 않음

### 2026-10-25T23:35:00+09:00 — 계획서 검증 확정

- TASK_ID: PC2-EYECARE-PROTOCOL-009-FINALIZATION-002
- EXECUTION_HOST: SVG-SKLEE (PC2)
- BRANCH: feat/clinical-protocol-validation-009
- BASE_HEAD: 8fba4bfe59ccd28841653cfc55510852e1256ba3
- HEAD: 8fba4bfe59ccd28841653cfc55510852e1256ba3. 커밋 없음
- START_TIME_KST: 2026-10-25T23:35:00+09:00
- END_TIME_KST: 2026-10-25T23:41:49+09:00
- ELAPSED: PT6M49S
- STATUS: CLINICAL_APPROVAL_PENDING. 추출 규칙은 권고만 하고 기본값은 꺼짐
- TEST_RESULTS: 합성 SQLite 15 passed, 1 skipped, exit 0. 일회용 PostgreSQL 15 `127.0.0.1:55441`에서 `medi010_external_clinical_import`까지 올린 뒤 합성 1 passed, exit 0. 컨테이너 `eyecare-protocol-009-final-pg`는 삭제함. pytest 종료 후 Python 프로세스는 없음
- REPRESENTATION: OSDI 문항 라벨 2,868. 단위 문자만 있는 OSDI 점수·개수 각 60. TBUT 항목마다 초만 있는 칸 61. 쉬르머 표준 `mm` 477, `mm`+`min` 철자 121. 코 자극은 그 철자 598. 오류로 세지 않음
- REMAINING_ISSUES: 서명 승인, ±3일과 ±7일, 방문 6 OSDI 그림, 반올림 자릿수, 단위 문자만 있는 칸의 의미, 연구 귀속, R1 운영 승인, 반복 양식 원본 키. 상세는 `CLINICAL-CLARIFICATION-REGISTER.md`
- NEXT_APPROVAL: 커밋과 푸시 없음. 게시된 Phase 009와 main, PC1, Draft PR은 변경하지 않음. Phase 010은 시작하지 않음

### 2026-10-25T13:03:02+09:00 — 계획서 대조

- TASK_ID: PC2-EYECARE-PROTOCOL-VALIDATION-009
- EXECUTION_HOST: SVG-SKLEE (PC2)
- BRANCH: feat/clinical-protocol-validation-009
- BASE_HEAD: 8fba4bfe59ccd28841653cfc55510852e1256ba3
- START_TIME_KST: 2026-10-25T13:03:02+09:00
- END_TIME_KST: 2026-10-25T13:13:30+09:00
- ELAPSED: PT10M28S
- PROTOCOL_SHA256: 39c51490afb38c8b44aebbaaa4a5bb9186e29d29292fb1726138462272fbff91
- EXCEL_SHA256: 1e0ece3a285e2e18fdc4a71999b2a4de680b2dce97ffa0fad0f0a8d773f80dab
- STATUS: PARTIALLY_VERIFIED. 서명 승인과 방문 허용기간은 UNRESOLVED 또는 CONFLICTING. 규칙 묶음은 EXTRACTED이며 기본 가져오기에서 꺼져 있다
- TEST_RESULTS: 합성 SQLite 15 passed, 1 skipped, exit 0. 일회용 PostgreSQL 15 합성 1 passed, exit 0, 컨테이너 삭제. 원본은 읽기 전용 집계만 했고 DB에 넣지 않음
- ADVISORY_COUNTS: OSDI 반올림 권고 207, 점수 불일치 0, TBUT 평균 불일치 0
- REMAINING_ISSUES: 방문 허용 ±3일과 ±7일. OSDI 점수 칸 60행과 TBUT 비숫자 122눈, 쉬르머 비숫자 121칸. 연구 귀속의 외부 증거. CM/DE/AE/CT/DS/EX 정규 모델
- NEXT_APPROVAL: 커밋과 푸시 없음. Phase 010은 시작하지 않음

### 2026-10-25T12:07:03+09:00 — Phase 009 게시

- TASK_ID: PC2-EYECARE-PHASE009-PUBLICATION-002
- EXECUTION_HOST: SVG-SKLEE (PC2)
- BRANCH: feat/external-clinical-import-009
- HEAD_BEFORE: 1a92a4fae86598c903f4434f2b6a87ed0118b1cd
- CODE_COMMIT: f5ef3295662a23da99b42fc1aadcac5eec35c8fd `feat: implement external clinical import and optional R1 linkage`
- DOCS_COMMIT: 이 문서 커밋
- START_TIME_KST: 2026-10-25T12:07:03+09:00
- END_TIME_KST: 2026-10-25T12:08:24+09:00
- ELAPSED: PT1M21S
- TEST_RESULTS: 이번 합성 SQLite 11 passed, 1 skipped, exit 0. pytest 종료 후 Python 프로세스와 aiosqlite 워커는 남지 않음. PostgreSQL은 이번 게시에서 다시 실행하지 않음. 이전 격리 증거는 2026-10-25T10:38 기록의 일회용 PostgreSQL 15 `medi010`과 합성 1 passed이며 컨테이너는 그때 삭제됨
- R1_DEFAULT: `enable_r1` 기본값은 false. 켜지 않으면 스크리닝 `SUBJID` 없는 행을 정규 대상자나 Visit로 올리지 않음
- GIT_EXCLUSION: `data/` 엑셀은 `.gitignore`의 `data/`에 걸림. `timeseries_analysis_summary.json`과 `data/README.md`는 이번 커밋에 넣지 않음
- PUSH: origin `feat/external-clinical-import-009`만. force push, main 병합, PC1 통합 브랜치와 Draft PR 변경 없음
- REMAINING_ISSUES: 앞열 식별자 의미, CM/DE/AE/CT/DS/EX 정규 모델과 안정 키, 연구·사이트, 단위, OSDI 코드표, MEDI-DES-001 귀속은 REQUIRES_CLINICAL_CONFIRMATION
- NEXT_APPROVAL: Phase 010은 시작하지 않음

### 2026-10-25T10:38:00+09:00 — R1 개발 연결 검증

- TASK_ID: PC2-EYECARE-PHASE009-LINKAGE-FIX-002
- EXECUTION_HOST: SVG-SKLEE (PC2)
- BRANCH: feat/external-clinical-import-009
- HEAD: 1a92a4fae86598c903f4434f2b6a87ed0118b1cd
- START_TIME_KST: 2026-10-25T10:38:00+09:00
- END_TIME_KST: 2026-10-25T10:50:16+09:00
- ELAPSED: PT12M16S
- SOURCE_SHA256: 1e0ece3a285e2e18fdc4a71999b2a4de680b2dce97ffa0fad0f0a8d773f80dab
- SOURCE_BYTES: 369628
- MAPPING: `spec-paired-1+r1`. 기본값은 꺼져 있고 `enable_r1`일 때만 동작
- STATUS: SOURCE_CONFIRMED, DEVELOPMENT_RULE_APPROVED, IMPLEMENTED, VERIFIED_IN_ISOLATION. 식별자 의미의 최종 임상 승인과 운영 반입은 REQUIRES_CLINICAL_CONFIRMATION. Phase 010은 BLOCKED
- TEST_RESULTS: 합성 SQLite 11 passed, 1 skipped, exit 0. 일회용 PostgreSQL 15 `127.0.0.1:55439`에서 합성 가져오기 1 passed. 같은 호스트의 다른 일회용 DB에서 R1 집계 검증 후 컨테이너 `eyecare-phase009-r1-pg` 삭제. aiosqlite 워커는 시작하지 않음
- R1_COUNTS: 원본 행 759. 스크리닝 63. 고유 연결 725. 방문 연결 359, 그중 V2–V6 원본 행 296. 대상자 단위 스테이징 366. 모호 0. 미해결 34. 거절 0. 값 불일치 0. 방문일 모순 0. 동일 지문 중복 0
- VISIT_ENTITIES: V1 63, V2 60, V3 60, V4 60, V5 60, V6 56. `_V1.1`은 방문으로 세지 않음
- CANONICAL: 초안 관찰 3887, 확정 0, 검증 분류 4064. 대상자 단위 366행은 정규 테이블로 올리지 않음
- PRIVACY: 스테이징 본문에 앞열 헤더 키가 들어간 행 0. 배정 값은 저장하지 않음. 원본 워크북은 수정하지 않음
- REMAINING_ISSUES: 앞열 헤더는 직접 식별자 라벨이다. 이번 규칙은 그 칸의 정규화 토큰이 스크리닝 `SUBJID`와 유일하게 같을 때만 쓰는 개발 규칙이다. CM, DE, AE, CT, DS, EX의 정규 모델과 안정 키는 없다. 연구·사이트·단위·OSDI 코드표·MEDI-DES-001 귀속은 미해결
- NEXT_APPROVAL: 커밋은 하지 않음. 운영 반입과 Phase 010은 시작하지 않음

### 2026-10-25T10:10:54+09:00 — 엑셀 관계 분석

- TASK_ID: PC2-DEEVO-EXCEL-RELATIONSHIP-ANALYSIS-001
- EXECUTION_HOST: SVG-SKLEE (PC2)
- EYECARE_BRANCH: feat/external-clinical-import-009
- EYECARE_HEAD: 1a92a4fae86598c903f4434f2b6a87ed0118b1cd
- SVG_ANALYZER_BRANCH: main
- SVG_ANALYZER_HEAD: 1f6aec408dcbdc62a9b73e0b232bdb9e35833ece
- START_TIME_KST: 2026-10-25T10:10:54+09:00
- END_TIME_KST: 2026-10-25T10:18:15+09:00
- ELAPSED: PT7M21S
- SOURCE_SHA256: 1e0ece3a285e2e18fdc4a71999b2a4de680b2dce97ffa0fad0f0a8d773f80dab
- SOURCE_BYTES: 369628
- METHOD: 로컬 openpyxl 읽기 전용 검사. REA와 온톨로지에는 스프레드시트 연산이 없어 사용하지 않음. 셀 값은 Git에 넣지 않음
- RESULT: PARTIALLY_RESOLVED. 코드와 원본 워크북은 변경하지 않음. 커밋과 푸시 없음
- DEFERRED_696: 방문 시트 296행은 앞열 토큰이 스크리닝 `SUBJID` 집합에 속함. 방문 코드가 없는 400행 중 366행도 같은 조건이고, 34행은 그 칸이 비어 있음
- RECOVERABLE_IF_APPROVED: 토큰이 맞는 662행. 그중 현재 방문 규칙을 그대로 쓸 수 있는 행은 296행. 34행은 키가 없음
- NEXT_APPROVAL: 앞열을 대상자 키로 채택하는 결정은 사람 승인 전이다. Phase 010과 재가져오기는 시작하지 않음

### 2026-10-25T09:32:46+09:00 — Phase 009 게시

- TASK_ID: PC2-EYECARE-PHASE009-PUBLICATION-001
- EXECUTION_HOST: SVG-SKLEE
- PC_ROLE: PC2
- REPOSITORY: MEDI-IOT-EyeCare
- BRANCH: feat/external-clinical-import-009
- BASELINE_HEAD: 79848a924515ee72e8ed3f95af444a6aab60f750
- HEAD_BEFORE: 79848a924515ee72e8ed3f95af444a6aab60f750
- HEAD_AFTER: 이 게시 커밋
- START_TIME_KST: 2026-10-25T09:31:42+09:00
- END_TIME_KST: 2026-10-25T09:32:46+09:00
- ELAPSED: PT1M4S
- COMMIT: `feat: implement external clinical data import foundation`
- PUSH: origin `feat/external-clinical-import-009`만. force push와 main 병합 없음
- TEST_RESULTS: 이번 합성 SQLite 8 passed, 1 skipped, exit 0. 이번 일회용 PostgreSQL 15 `127.0.0.1:55438`에서 `medi010_external_clinical_import` upgrade 후 합성 가져오기 1 passed, exit 0. 컨테이너 삭제. 실데이터 사례는 다시 실행하지 않음
- REMAINING_ISSUES: 아래 A–E는 미해결 매핑 의존성이다. 보류 행은 가져온 것이 아니다
- NEXT_APPROVAL: PC1 통합은 이 게시에서 만들지 않음. Phase 010은 시작하지 않음

### 2026-10-25T01:01:03+09:00 — 일회용 DB 집계

- TASK_ID: PC2-EYECARE-CLINICAL-IMPORT-009
- EXECUTION_HOST: SVG-SKLEE
- PC_ROLE: PC2
- BRANCH: feat/external-clinical-import-009
- HEAD_BEFORE: 79848a924515ee72e8ed3f95af444a6aab60f750
- HEAD_AFTER: 79848a924515ee72e8ed3f95af444a6aab60f750
- START_TIME_KST: 2026-10-25T00:45:00+09:00
- END_TIME_KST: 2026-10-25T01:01:03+09:00
- ELAPSED: PT16M3S
- DATABASE: 일회용 PostgreSQL 15 `127.0.0.1:55437`, 이름 없는 데이터 디렉터리. 집계 후 컨테이너 삭제
- TEST_RESULTS: 합성 SQLite 8 passed, 1 skipped, exit 0. 같은 일회용 DB에서 합성 가져오기 1 passed
- REMAINING_ISSUES: 연구 코드 미확인. V2 이후 대상자 키 미해결. 커밋 없음

## 구조 집계

- 데이터 시트 17개, 정렬 확인 17개, 데이터 행 759개
- 스크리닝 번호가 있는 행에서 서로 다른 대상자 63명, 대상자-방문 쌍 63개
- 방문 코드별 행 수: V1 63, V2 60, V3 60, V4 60, V5 60, V6 56
- 방문일 결측 0, 방문일 해석 실패 0, 스크리닝 번호 결측 0
- 배정 칸 180개는 값을 저장하지 않음
- 코드표가 없어 `NEEDS_HUMAN_REVIEW`로만 분류한 칸 4064개. 입력 오류로 단정하지 않음

## 일회용 DB에 반영한 정규 행

스크리닝 시트만 `SUBJID`가 있어 정규 반영됐다.

- 대상자 63, Visit 63, 초안 관찰 819, 확정 관찰 0, OSDI 초안 응답 63
- 검증 분류 1008, 값 불일치 0
- 스테이징 상태: 반영 63행, 매핑 보류 696행
- 자동 확정과 자동 잠금은 하지 않음

V2 이후 시트는 대상자 항목이 없어 이름이나 병록번호로 잇지 않고 보류했다. 이 워크북이 MEDI-DES-001이라는 문구는 파일에 없다.

## R1 격리 검증

위 게시 시점의 696행 보류는 당시 구현 기준이다. 이번 개발 규칙에서는 앞열 토큰을 `SUBJID`와 같은 함수로 정규화하고, 스크리닝 집합과 정확히 하나 일치할 때만 연결한다. 대소문자가 다른 코드는 고치지 않고, 대소문자만 다른 후보가 둘 이상이면 거절한다. 빈 칸은 이전 행으로 채우지 않는다. 이름과 무작위 배정은 키로 쓰지 않는다.

V2–V6 원본 296행은 방문일 모순 없이 연결됐다. 같은 방문 코드의 시트가 둘 이상인 V3, V4도 방문일이 충돌하지 않았고 값 불일치는 0이었다. CM, DE, AE, CT, DS, EX 366행은 검증된 스테이징에만 남겼다. 빈 토큰 34행은 미해결이다. 이 집계는 임상 식별자 승인도, MEDI-DES-001 귀속도 아니다.

## 미해결 매핑 의존성

이름이나 인접 행으로 대상자를 연결하지 않는다. 대상자 단위 양식은 정규 임상 행으로 가져온 것이 아니다.

- A. 방문 원본 296행의 격리 연결은 개발 규칙으로 검증됐다. 빈 토큰 34행은 미해결이고, 대상자 단위 366행은 정규 모델이 없어 스테이징에 남는다.
- B. 연구와 사이트 귀속은 파일에서 확인되지 않았다.
- C. TBUT와 쉬르머의 측정 단위는 명세에 없다.
- D. OSDI 코드표의 권위 있는 원문이 없다.
- E. MEDI-DES-001 귀속은 워크북만으로 성립하지 않는다.
