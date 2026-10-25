# 외부 반출 데이터 사전

로컬 `data/`의 Excel 1건을 읽기 전용으로 해석했다. 바이트 크기는 369628이다. 워크시트는 34개이며 명세 17개와 데이터 17개가 쌍이다. 셀 값, 식별자, 측정값은 적지 않는다. 원본 파일은 Git에서 제외된다.

## 진행 기록

### 2026-10-26T00:09:57+09:00 — 단위 표현 게시

- TASK_ID: PC2-EYECARE-PROTOCOL009-PUBLICATION-003
- EXECUTION_HOST: SVG-SKLEE
- BRANCH: feat/clinical-protocol-validation-009
- CODE_COMMIT: 85ef271b96e36a1a60508d66ff71ae37264235ca
- DOCS_COMMIT: 이 문서 커밋
- START_TIME_KST: 2026-10-26T00:09:57+09:00
- END_TIME_KST: 2026-10-26T00:10:50+09:00
- ELAPSED: PT53S
- TEST_RESULTS: 이번 합성 SQLite 15 passed, 1 skipped, exit 0. PostgreSQL은 다시 실행하지 않음
- NEXT_APPROVAL: 식별자와 측정값은 문서에 넣지 않음. Phase 010은 시작하지 않음

### 2026-10-25T23:35:00+09:00 — 단위 표현

- TASK_ID: PC2-EYECARE-PROTOCOL-009-FINALIZATION-002
- EXECUTION_HOST: SVG-SKLEE
- BRANCH: feat/clinical-protocol-validation-009
- HEAD: 8fba4bfe59ccd28841653cfc55510852e1256ba3
- START_TIME_KST: 2026-10-25T23:35:00+09:00
- END_TIME_KST: 2026-10-25T23:41:49+09:00
- ELAPSED: PT6M49S
- OSDI 점수·개수와 TBUT에는 계획서 단위 문자만 있는 칸이 있다. 쉬르머 일부는 `mm`, 일부는 `mm`과 `min`이 이어진 다섯 글자다. 의미는 UNRESOLVED
- TEST_RESULTS: 합성 SQLite 15 passed, 1 skipped, exit 0. 일회용 PostgreSQL 15 `127.0.0.1:55441`에서 `medi010_external_clinical_import`까지 올린 뒤 합성 1 passed, exit 0. 컨테이너 `eyecare-protocol-009-final-pg`는 삭제함. pytest 종료 후 Python 프로세스는 없음
- NEXT_APPROVAL: 커밋과 푸시 없음. Phase 010은 시작하지 않음

### 2026-10-25T13:03:02+09:00 — 계획서 1.3과 명세 코드

- TASK_ID: PC2-EYECARE-PROTOCOL-VALIDATION-009
- EXECUTION_HOST: SVG-SKLEE
- BRANCH: feat/clinical-protocol-validation-009
- BASE_HEAD: 8fba4bfe59ccd28841653cfc55510852e1256ba3
- START_TIME_KST: 2026-10-25T13:03:02+09:00
- END_TIME_KST: 2026-10-25T13:13:30+09:00
- ELAPSED: PT10M28S
- OSQ1-5 코드는 선택 번호와 임상 점수 0-4를 같이 적는다. OSQ6-12는 해당없음을 포함한다
- 저장값이 그 라벨과 같을 때만 권고 규칙이 점수로 읽는다. 기본 가져오기는 라벨을 점수로 바꾸지 않는다
- TBUT 단위는 초, 쉬르머 단위는 mm/5min, 방법은 비마취다. 이 메타데이터는 승인 전 규칙에만 있다
- REMAINING_ISSUES: 방문 허용기간 충돌. 연구 귀속은 워크북만으로 확정하지 않음

### 2026-10-25T12:07:03+09:00 — 게시 기록

- TASK_ID: PC2-EYECARE-PHASE009-PUBLICATION-002
- EXECUTION_HOST: SVG-SKLEE
- BRANCH: feat/external-clinical-import-009
- HEAD_BEFORE: 1a92a4fae86598c903f4434f2b6a87ed0118b1cd
- CODE_COMMIT: f5ef3295662a23da99b42fc1aadcac5eec35c8fd
- START_TIME_KST: 2026-10-25T12:07:03+09:00
- END_TIME_KST: 2026-10-25T12:08:24+09:00
- ELAPSED: PT1M21S
- TEST_RESULTS: 합성 SQLite 11 passed, 1 skipped, exit 0. PostgreSQL은 다시 실행하지 않음
- REMAINING_ISSUES: R1은 선택 사항이며 임상 식별자 승인이 아님

### 2026-10-25T10:38:00+09:00 — R1 매핑 초안

- TASK_ID: PC2-EYECARE-PHASE009-LINKAGE-FIX-002
- EXECUTION_HOST: SVG-SKLEE
- BRANCH: feat/external-clinical-import-009
- HEAD: 1a92a4fae86598c903f4434f2b6a87ed0118b1cd
- SOURCE_SHA256: 1e0ece3a285e2e18fdc4a71999b2a4de680b2dce97ffa0fad0f0a8d773f80dab
- START_TIME_KST: 2026-10-25T10:38:00+09:00
- END_TIME_KST: 2026-10-25T10:50:16+09:00
- ELAPSED: PT12M16S
- STATUS: DEVELOPMENT_RULE_APPROVED, IMPLEMENTED, VERIFIED_IN_ISOLATION, REQUIRES_CLINICAL_CONFIRMATION
- 매핑 버전 `spec-paired-1+r1`은 옵션이다. 끄면 스크리닝 `SUBJID`만 정규 키가 된다
- 앞열 토큰은 정수형 수를 정수 문자열로 만들고 앞뒤 공백만 제거한다. 스크리닝 `SUBJID`와 완전히 같을 때만 받는다
- CM 선행병용약물, DE 의료기기, AE 이상사례, CT 선행병용요법, DS 시험 종료, EX MEDI-EYE 치료는 대상자 단위 스테이징이다. 정규 엔티티는 아직 없다

### 2026-10-25T10:10:54+09:00 — 앞열과 스크리닝 번호의 구조 비교

- TASK_ID: PC2-DEEVO-EXCEL-RELATIONSHIP-ANALYSIS-001
- EXECUTION_HOST: SVG-SKLEE
- BRANCH: feat/external-clinical-import-009
- HEAD: 1a92a4fae86598c903f4434f2b6a87ed0118b1cd
- SOURCE_SHA256: 1e0ece3a285e2e18fdc4a71999b2a4de680b2dce97ffa0fad0f0a8d773f80dab
- START_TIME_KST: 2026-10-25T10:10:54+09:00
- END_TIME_KST: 2026-10-25T10:18:15+09:00
- ELAPSED: PT7M21S
- 스크리닝 두 시트의 63행에서 앞열 `병록번호` 텍스트는 같은 행의 `SUBJID`와 일치했다. 다른 15개 데이터 시트에는 `SUBJID` 항목이 없다.
- 방문 시트 296행과 방문 코드가 없는 시트 366행의 앞열 토큰은 스크리닝 `SUBJID` 집합 안이다. 집합 밖 토큰은 0개다.
- 선행병용약물 33행과 이상사례 1행은 앞쪽 다섯 열이 모두 비어 있고 병합 셀도 없다. 이 34행의 대상자 연결은 확정하지 않았다.
- 승인된 매핑은 그대로다. `병록번호`를 `subject_code`로 쓰는 변경은 구현하지 않았다.

### 2026-10-25T09:32:46+09:00 — 미해결 매핑을 게시 기록에 고정

- TASK_ID: PC2-EYECARE-PHASE009-PUBLICATION-001
- EXECUTION_HOST: SVG-SKLEE
- BRANCH: feat/external-clinical-import-009
- HEAD_BEFORE: 79848a924515ee72e8ed3f95af444a6aab60f750
- HEAD_AFTER: 이 게시 커밋
- START_TIME_KST: 2026-10-25T09:31:42+09:00
- END_TIME_KST: 2026-10-25T09:32:46+09:00
- ELAPSED: PT1M4S
- REMAINING_ISSUES: A 696행 보류, B 연구·사이트 미확인, C 단위 미확인, D OSDI 코드표 없음, E MEDI-DES-001 미귀속

### 2026-10-25T01:01:03+09:00 — 식별자 제거 사전

- TASK_ID: PC2-EYECARE-CLINICAL-IMPORT-009
- EXECUTION_HOST: SVG-SKLEE
- BRANCH: feat/external-clinical-import-009
- HEAD_BEFORE: 79848a924515ee72e8ed3f95af444a6aab60f750
- START_TIME_KST: 2026-10-25T00:45:00+09:00
- END_TIME_KST: 2026-10-25T01:01:03+09:00
- ELAPSED: PT16M3S
- REMAINING_ISSUES: 연구 코드와 사이트 코드는 파일에 없음

## 확인된 구조

명세 헤더는 `Domain`, `Item ID`, `Item Label`, `Code`, `Layout`, `Type`, `Required`다. 각 데이터 시트의 항목 라벨은 직전 명세와 오프셋 5에서 불일치 0으로 맞는다.

앞 5개 열은 `작성일자`, `병록번호`, `이름`, `성별`, `나이`다. `병록번호`와 `이름`은 직접 식별자로 보고 해시만 남긴다. 이름과 배정 값은 대상자 키가 아니다. R1이 켜진 경우에만 앞열 토큰의 정규화 결과가 스크리닝 `SUBJID`와 유일하게 같으면 그 번호를 쓴다.

## 확정 매핑

| 원본 | 정규 대상 | 근거 |
|---|---|---|
| `SUBJID` 스크리닝 번호 | `StudySubject.subject_code` | 명세 항목 ID. 스크리닝 시트에만 있음 |
| 앞열 토큰, R1이 켜진 경우 | 같은 `subject_code` | 스크리닝 `SUBJID`와 정규화 결과가 유일하게 같을 때만. 헤더를 병록번호 조회로 쓰지 않음 |
| 시트 제목의 `V숫자 (` | `StudyVisit.visit_code` | `_V1.1` 양식 버전은 방문이 아님 |
| `SVDAT` | `StudyVisit.occurred_on` | 해당 행의 값. 빈 값은 만들지 않음 |
| CM, DE, AE, CT, DS, EX | 검증된 스테이징 | 정규 모델과 안정 원본 키가 생기기 전에는 승격하지 않음 |
| `TBODORS1-3`, `TBOSORS1-3` | 관찰 `TBUT`, 좌우, 반복 | 항목 ID와 좌우 시행 항목의 인접 |
| `TBODORSAV`, `TBOSORSAV` | 관찰 `TBUT` 보고 평균 | 같은 눈 블록의 평균 항목 |
| `STODORS`, `STOSORS` | 관찰 `SCHIRMER` | 항목 ID |
| `OSQ1-12` | 설문 `OSDI` 초안 문항 | 명세 라벨 |
| `OSSCORE` | 관찰 `OSDI_SCORE` | 명세 항목 ID |

단위는 명세에 없어 UNRESOLVED다. 관찰 `unit`은 비운다.

## 미해결

- 연구 코드와 사이트 코드는 파일에 없다. `MEDI-DES-001` 문자열도 없다.
- R1은 이 워크북의 개발 검증용이다. 다른 EDC 반출에 일반화하지 않는다.
- 앞열 헤더의 임상 의미는 아직 확정되지 않았다. 값이 스크리닝 번호와 같다는 구조 증거만 있다.
- CM, DE, AE, CT, DS, EX는 반복 행의 안정 키가 없다. 행 번호만으로 정규 ID를 만들지 않는다.
- `RN` 도메인과 무작위 배정 라벨은 값을 저장하지 않는다.
- OSDI 문항의 코드표와 쉬르머 텍스트 토큰은 확정하지 않았다.
- 이상사례, 병용약, 치료 시트는 스테이징만 하고 정규 관찰로 만들지 않는다.
- 같은 방문 코드의 데이터 시트가 둘인 경우가 있다. 목적 차이는 UNRESOLVED다.
