# 외부 임상 데이터 가져오기 명세

요구 ID는 `EYECARE-CLINICAL-IMPORT-001`이다. Phase 008에서는 코드를 추가하지 않았다. Phase 009 브랜치 `feat/external-clinical-import-009`에서 명세 짝 파이프라인을 구현했다. Alembic 개정 `medi009_clinical_data_lock`은 Phase 008 스키마이고, `medi010_external_clinical_import`는 가져오기 스테이징이다. 둘 다 개발 단계 번호가 아니다.

## 진행 기록

### 2026-10-26T15:51:33+09:00 — 1.10 권고 게시

- TASK_ID: PC2-EYECARE-PROTOCOL-V110-PUBLICATION-004
- EXECUTION_HOST: SVG-SKLEE
- BRANCH: feat/clinical-protocol-validation-009
- CODE_COMMIT: 574b9527fbed211d6ef2f75699888f8db58f50d6
- DOCS_COMMIT: 이 문서 커밋
- START_TIME_KST: 2026-10-26T15:51:33+09:00
- END_TIME_KST: 2026-10-26T15:53:37+09:00
- ELAPSED: PT2M4S
- 선택 가능한 묶음은 `medi-des-001-v1.10`이다. `medi-des-001-v1.3`은 이력으로만 남고 호출하면 거부한다
- TEST_RESULTS: 합성 SQLite 15 passed, 1 skipped, exit 0. 일회용 PostgreSQL 15 합성 1 passed, exit 0
- NEXT_APPROVAL: HTTP 본문에 권고 선택자는 없다. Phase 010은 시작하지 않음

### 2026-10-26T15:01:00+09:00 — 규칙 묶음 1.10

- TASK_ID: 로컬 계획서 1.10 반영
- EXECUTION_HOST: SVG-SKLEE
- BRANCH: feat/clinical-protocol-validation-009
- START_TIME_KST: 2026-10-26T15:01:00+09:00
- END_TIME_KST: 2026-10-26T15:04:39+09:00
- ELAPSED: PT3M39S
- `protocol_advisory_id`의 현재 값은 `medi-des-001-v1.10`이다. 기본값은 비어 있고 HTTP 본문에는 없다
- TEST_RESULTS: 합성 SQLite 15 passed, 1 skipped, exit 0. PostgreSQL은 다시 실행하지 않음
- NEXT_APPROVAL: 커밋과 푸시 없음. Phase 010은 시작하지 않음

### 2026-10-26T00:09:57+09:00 — 권고 가져오기 게시

- TASK_ID: PC2-EYECARE-PROTOCOL009-PUBLICATION-003
- EXECUTION_HOST: SVG-SKLEE
- BRANCH: feat/clinical-protocol-validation-009
- BASE_HEAD: 8fba4bfe59ccd28841653cfc55510852e1256ba3
- CODE_COMMIT: 85ef271b96e36a1a60508d66ff71ae37264235ca
- DOCS_COMMIT: 이 문서 커밋
- START_TIME_KST: 2026-10-26T00:09:57+09:00
- END_TIME_KST: 2026-10-26T00:10:50+09:00
- ELAPSED: PT53S
- API `ImportBody`에는 `protocol_advisory_id`가 없고 `enable_r1` 기본값은 false
- TEST_RESULTS: 이번 합성 SQLite 15 passed, 1 skipped, exit 0. PostgreSQL은 다시 실행하지 않음
- NEXT_APPROVAL: 자동 확정과 자동 잠금은 없음. Phase 010은 시작하지 않음

### 2026-10-25T23:35:00+09:00 — 기본 꺼짐 재확인

- TASK_ID: PC2-EYECARE-PROTOCOL-009-FINALIZATION-002
- EXECUTION_HOST: SVG-SKLEE
- BRANCH: feat/clinical-protocol-validation-009
- HEAD: 8fba4bfe59ccd28841653cfc55510852e1256ba3
- START_TIME_KST: 2026-10-25T23:35:00+09:00
- END_TIME_KST: 2026-10-25T23:41:49+09:00
- ELAPSED: PT6M49S
- API `ImportBody.enable_r1` 기본값은 false이고 `protocol_advisory_id`는 요청 본문에 없다
- 원본 OSDI 라벨과 숫자 관찰은 권고 계산이 덮어쓰지 않는다. TBUT 평균 권고도 관찰을 만들지 않는다
- TEST_RESULTS: 합성 SQLite 15 passed, 1 skipped, exit 0. 일회용 PostgreSQL 15 `127.0.0.1:55441`에서 `medi010_external_clinical_import`까지 올린 뒤 합성 1 passed, exit 0. 컨테이너 `eyecare-protocol-009-final-pg`는 삭제함. pytest 종료 후 Python 프로세스는 없음
- NEXT_APPROVAL: 확인 등록부 작성. 커밋과 푸시 없음. Phase 010은 시작하지 않음

### 2026-10-25T13:03:02+09:00 — 선택적 계획서 권고

- TASK_ID: PC2-EYECARE-PROTOCOL-VALIDATION-009
- EXECUTION_HOST: SVG-SKLEE
- BRANCH: feat/clinical-protocol-validation-009
- BASE_HEAD: 8fba4bfe59ccd28841653cfc55510852e1256ba3
- START_TIME_KST: 2026-10-25T13:03:02+09:00
- END_TIME_KST: 2026-10-25T13:13:30+09:00
- ELAPSED: PT10M28S
- `protocol_advisory_id` 기본값은 비어 있다. `medi-des-001-v1.3`일 때만 권고 소견을 추가한다
- `enable_r1` 기본값은 계속 false다
- 매핑 버전은 권고를 켠 경우에만 `+advisory-medi-des-001-v1.3`가 붙는다
- NEXT_APPROVAL: 규칙은 ACTIVE가 아니다. Phase 010은 시작하지 않음

### 2026-10-25T12:07:03+09:00 — Phase 009 게시

- TASK_ID: PC2-EYECARE-PHASE009-PUBLICATION-002
- EXECUTION_HOST: SVG-SKLEE
- BRANCH: feat/external-clinical-import-009
- HEAD_BEFORE: 1a92a4fae86598c903f4434f2b6a87ed0118b1cd
- CODE_COMMIT: f5ef3295662a23da99b42fc1aadcac5eec35c8fd
- START_TIME_KST: 2026-10-25T12:07:03+09:00
- END_TIME_KST: 2026-10-25T12:08:24+09:00
- ELAPSED: PT1M21S
- TEST_RESULTS: 합성 SQLite 11 passed, 1 skipped, exit 0. PostgreSQL은 이번 게시에서 다시 실행하지 않음
- R1_DEFAULT: false
- NEXT_APPROVAL: Phase 010은 BLOCKED

### 2026-10-25T10:38:00+09:00 — R1 연결 규칙

- TASK_ID: PC2-EYECARE-PHASE009-LINKAGE-FIX-002
- EXECUTION_HOST: SVG-SKLEE
- BRANCH: feat/external-clinical-import-009
- HEAD: 1a92a4fae86598c903f4434f2b6a87ed0118b1cd
- START_TIME_KST: 2026-10-25T10:38:00+09:00
- END_TIME_KST: 2026-10-25T10:50:16+09:00
- ELAPSED: PT12M16S
- MAPPING: `specification_paired`의 선택 버전 `spec-paired-1+r1`
- STATUS: IMPLEMENTED, VERIFIED_IN_ISOLATION, REQUIRES_CLINICAL_CONFIRMATION
- TEST_RESULTS: 합성 SQLite 11 passed, 1 skipped, exit 0. 일회용 PostgreSQL 15 합성 1 passed, exit 0. 원본 집계는 검증 보고에만 적음
- REMAINING_ISSUES: 대상자 단위 양식의 정규 모델, 안정 원본 키, 연구·사이트 귀속, 단위, OSDI 코드표
- NEXT_APPROVAL: 커밋과 운영 반입은 이 작업에 포함되지 않음. Phase 010은 BLOCKED

R1은 앞열 토큰을 `normalize_subject_token`으로 바꾼 뒤 스크리닝 `SUBJID` 집합과 완전 일치할 때만 받는다. 이름, 병록번호 자체의 추론, 배정 번호는 키로 쓰지 않는다. 원본 앞열은 해시로만 스테이징에 남고 관찰 값에는 넣지 않는다. 방문은 시트 제목의 `V숫자 (`, 그 행의 `SVDAT`, 호출자가 준 연구·사이트, 시트 이름과 양식 버전으로 구분한다. 양식 버전 `_V1.1`은 Visit가 아니다. CM, DE, AE, CT, DS, EX는 `subject_level_staged`이며 `ClinicalObservation`이나 `StudyVisit`로 만들지 않는다.

### 2026-10-25T09:32:46+09:00 — Phase 009 게시

- TASK_ID: PC2-EYECARE-PHASE009-PUBLICATION-001
- EXECUTION_HOST: SVG-SKLEE
- PC_ROLE: PC2
- BRANCH: feat/external-clinical-import-009
- HEAD_BEFORE: 79848a924515ee72e8ed3f95af444a6aab60f750
- HEAD_AFTER: 이 게시 커밋
- START_TIME_KST: 2026-10-25T09:31:42+09:00
- END_TIME_KST: 2026-10-25T09:32:46+09:00
- ELAPSED: PT1M4S
- COMMIT: `feat: implement external clinical data import foundation`
- PUSH: origin `feat/external-clinical-import-009`만
- REMAINING_ISSUES: A 696행은 미반입. B 연구·사이트, C 단위, D OSDI 코드표, E MEDI-DES-001 귀속은 미해결

### 2026-10-25T01:01:03+09:00 — Phase 009 가져오기 구현

- TASK_ID: PC2-EYECARE-CLINICAL-IMPORT-009
- EXECUTION_HOST: SVG-SKLEE
- PC_ROLE: PC2
- REPOSITORY: MEDI-IOT-EyeCare
- BRANCH: feat/external-clinical-import-009
- HEAD_BEFORE: 79848a924515ee72e8ed3f95af444a6aab60f750
- HEAD_AFTER: 79848a924515ee72e8ed3f95af444a6aab60f750
- START_TIME_KST: 2026-10-25T00:45:00+09:00
- END_TIME_KST: 2026-10-25T01:01:03+09:00
- ELAPSED: PT16M3S
- ADAPTER: `specification_paired` `spec-paired-1`. 특정 시트 이름을 고정하지 않음
- MIGRATION: `medi010_external_clinical_import`. Alembic 개정명이며 개발 단계 010이 아님
- TEST_RESULTS: 합성 SQLite 8 passed, PostgreSQL 전용 1 skipped, exit 0. 일회용 PostgreSQL 15에서 같은 합성 테스트 1 passed 후 컨테이너 삭제
- CASE_STUDY: 로컬 일회용 DB에만 반영하고 집계만 기록. 원본 워크북은 수정하지 않음. 컨테이너 삭제
- REMAINING_ISSUES: 파일 안에 연구 코드와 사이트 코드가 없음. V2 이후 시트에 SUBJID가 없어 방문 연결은 UNRESOLVED. 커밋과 push 없음
- NEXT_APPROVAL: 결과 검토 후 커밋. Phase 010은 시작하지 않음

### 2026-10-24T17:28:14+09:00 — 가져오기 명세 게시

- TASK_ID: PC2-EYECARE-PHASE008-PUBLICATION-001
- EXECUTION_HOST: SVG-SKLEE
- PC_ROLE: PC2
- REPOSITORY: MEDI-IOT-EyeCare
- LOCAL_PATH: C:\Office_Automation\MEDI-IOT-EyeCare
- BRANCH: feat/clinical-data-lock-008
- HEAD_BEFORE: a8e32651c592cb30de27706c1d4c5c95c44c82c9
- HEAD_AFTER: 이 문서 커밋
- START_TIME_KST: 2026-10-24T17:27:38+09:00
- END_TIME_KST: 2026-10-24T17:28:14+09:00
- ELAPSED: PT36S
- FILES_CHANGED: 이 명세를 포함한 문서 4건. 가져오기 코드는 없음
- TEST_RESULTS: 가져오기 테스트는 없음. 잠금 SQLite 재실행 42 passed, 3 skipped, exit 0
- COMMIT: `docs: finalize Phase 008 clinical data lock specifications`
- PUSH: origin `feat/clinical-data-lock-008`만
- REMAINING_ISSUES: EYECARE-CLINICAL-IMPORT-001은 DEFERRED

### 2026-10-24T17:11:37+09:00 — 가져오기 명세만 작성

- TASK_ID: PC2-EYECARE-CLINICAL-SUPPORT-008
- EXECUTION_HOST: SVG-SKLEE
- PC_ROLE: PC2
- REPOSITORY: MEDI-IOT-EyeCare
- LOCAL_PATH: C:\Office_Automation\MEDI-IOT-EyeCare
- BRANCH: feat/clinical-data-lock-008
- HEAD_BEFORE: a8e32651c592cb30de27706c1d4c5c95c44c82c9
- HEAD_AFTER: a8e32651c592cb30de27706c1d4c5c95c44c82c9
- START_TIME_KST: 2026-10-24T17:08:00+09:00
- END_TIME_KST: 2026-10-24T17:11:37+09:00
- ELAPSED: PT3M37S
- FILES_CHANGED: 이 명세. 가져오기 코드, Excel, 환자 기록은 없음
- TEST_RESULTS: 가져오기 테스트는 없음. 기존 잠금 SQLite 42 passed, 3 skipped, exit 0. 일회용 PostgreSQL 15 1 passed, exit 0
- REMAINING_ISSUES: 구현은 DEFERRED. DeeVo는 접근하지 않음. 커밋과 push 없음
- NEXT_APPROVAL: 합성 파일 가져오기 착수는 별도 범위 승인

## 범위

인가된 외부 EDC가 내보낸 Excel 또는 CSV를 EYECARE 정규 임상 엔티티로 반영한다.

- 원본 파일, SHA-256, 출처, 수신 시각을 불변으로 보존한다.
- 외부 필드를 연구, 사이트, 대상자, Visit, 관찰, 설문 응답으로 명시적으로 매핑한다.
- 최종 반영 전에 스테이징과 검증을 둔다.
- 중복을 검출하고 같은 원본의 재가져오기를 멱등으로 처리한다.
- 여러 내보내기 스냅샷을 비교하고 이전 개정을 지우지 않는다.
- 반영과 거절은 기존 감사 이벤트에 남긴다.
- 반영된 기록은 Phase 007 품질 실행 대상이 된다.
- 이후 AI 이상 탐지는 `EYECARE-CLINICAL-AI-QC-001`의 권고이며 가져오기가 원본을 덮어쓰지 않는다.

대상자와 Visit 중심 조회는 `EYECARE-CLINICAL-UX-001`의 인가된 읽기다. 가져오기가 임상 기록을 복제하지 않는다.

## 첫 사례 후보

MEDI-DES-001 탐색 임상시험의 스폰서 인가 DeeVo Excel이다. DeeVo 자체는 읽기 전용이다. EYECARE 안에서의 반영, 수정, 질의, 잠금은 기존 권한과 감사를 통과할 때만 가능하다. 맹검 정보는 매핑하지 않는다. Visit 창, 문항, 임상 임계값은 승인된 프로토콜 원문이 생기기 전에 공통 규칙으로 만들지 않는다.

자동 개발 테스트에는 합성 파일만 쓴다. 실제 환자 정보와 운영 내보내기는 Phase 008에 포함하지 않는다.

## 의존성

- 정규 임상 수명주기와 개정.
- Phase 007 질의와 품질 실행.
- Phase 008 잠금. 가져온 확정 기록은 이후 같은 준비도 규칙을 받는다.
- 승인된 연구 프로토콜. 없으면 준비도는 `BLOCKED_PENDING_PROTOCOL`이다.
- UX-001과 AI-QC-001은 별도 요구이며 가져오기 완료 조건이 아니다.

## 수용 기준

1. 원본 바이트와 SHA-256이 반영 후에도 그대로다.
2. 매핑되지 않은 열은 최종 관찰이 되지 않고 스테이징에 남는다.
3. 같은 연구와 같은 원본 해시를 다시 처리해도 대상자, Visit, 관찰이 늘지 않는다.
4. 새 스냅샷은 이전 확정 개정을 삭제하지 않고 차이를 보여 준다.
5. 반영된 관찰의 값 변경은 기존 정정 경로와 감사를 통과한다.
6. 가져오기 함수가 잠금을 걸거나 질의와 품질 소견을 닫지 않는다.
7. 권한 없는 사이트는 스테이징 행을 읽지 못한다.
8. 개발 테스트 픽스처에 환자 식별자와 DeeVo 자격 증명이 없다.

## 후보 순서

승인된 단계 번호가 아니다.

1. 합성 파일로 스테이징, 해시, 멱등을 검증한다.
2. 스폰서 승인과 승인된 매핑 원문이 있은 뒤 MEDI-DES-001 사례를 검증한다.
3. 품질 실행과 잠금은 반영된 정규 기록에 기존 서비스를 적용한다.
4. 탐색 화면과 AI 권고는 각 요구의 별도 승인 뒤에 연결한다.
