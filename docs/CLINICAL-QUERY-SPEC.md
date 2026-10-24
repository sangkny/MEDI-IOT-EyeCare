# 임상 질의 명세

질의는 연구 데이터와 분리된 업무 기록이다. 해결이나 재오픈은 관찰 값을 바꾸지 않는다. 정정이 필요하면 기존 개정 서비스를 명시적으로 호출하고, 이전 관찰 행은 남긴다.

## 진행 기록

### 2026-10-24T16:45:06+09:00 — Phase 008 게시

- TASK_ID: PC2-EYECARE-PHASE008-PUBLISH-001
- EXECUTION_HOST: SVG-SKLEE
- BRANCH: feat/clinical-data-lock-008
- HEAD_BEFORE: 87aea032d7af8ec1723036a9ca7c1183dcdbd7a3
- HEAD_AFTER: 이 게시 커밋
- START_TIME_KST: 2026-10-24T16:44:02+09:00
- END_TIME_KST: 2026-10-24T16:45:06+09:00
- TEST_RESULTS: 질의 회귀 포함 SQLite 42 passed, 3 skipped
- PUSH: origin `feat/clinical-data-lock-008`만

### 2026-10-23T20:28:50+09:00 — Phase 008 잠금과 질의

- TASK_ID: EYECARE-CLINICAL-SUPPORT-008
- EXECUTION_HOST: SVG-SKLEE
- PC_ROLE: PC2
- REPOSITORY: MEDI-IOT-EyeCare
- LOCAL_PATH: C:\Office_Automation\MEDI-IOT-EyeCare
- BRANCH: feat/clinical-data-lock-008
- HEAD_BEFORE: 87aea032d7af8ec1723036a9ca7c1183dcdbd7a3
- HEAD_AFTER: 87aea032d7af8ec1723036a9ca7c1183dcdbd7a3
- START_TIME_KST: 2026-10-23T20:04:00+09:00
- END_TIME_KST: 2026-10-23T20:28:50+09:00
- ELAPSED: PT24M50S
- FILES_CHANGED: `services/clinical_lock.py`. 질의 서비스의 상태 기계는 유지
- TEST_RESULTS: 미해결 error 질의가 있으면 `BLOCKED_BY_QUERY`. 잠금이 질의 상태를 닫지 않음. SQLite 20 passed
- MIGRATION: 질의 테이블 변경 없음
- REMAINING_ISSUES: 화면 없음. 잠금 중 정정은 거부
- NEXT_APPROVAL: 커밋 후 질의 화면은 별도 단계

### 2026-10-23 09:15 KST — Phase 007 검증

- TASK_ID: PC2-CLINICAL-PHASE007-CHECKPOINT-001
- EXECUTION_HOST: SVG-SKLEE
- PC_ROLE: PC2
- REPOSITORY: MEDI-IOT-EyeCare
- LOCAL_PATH: C:\Office_Automation\MEDI-IOT-EyeCare
- BRANCH: feat/clinical-query-quality-007
- HEAD_BEFORE: a8661d5ab665f686b2e81ef9c0be1e8f633c8e93
- HEAD_AFTER: 기능 커밋에 포함
- START_TIME_KST: 2026-10-23T09:14:23+09:00
- END_TIME_KST: 2026-10-23T09:15:49+09:00
- FILES_CHANGED: 질의 수명주기와 이 명세
- TEST_RESULTS: 전이, 재오픈, 이력, 사이트 격리, 원본 관찰 유지 PASS. PostgreSQL 동시 해결 1 passed
- REMAINING_ISSUES: 화면과 잠금 업무는 없음

### 2026-10-23 00:35 KST — Phase 007 임상 질의

- TASK_ID: EYECARE-CLINICAL-SUPPORT-007
- EXECUTION_HOST: SVG-SKLEE
- PC_ROLE: PC2
- REPOSITORY: MEDI-IOT-EyeCare
- LOCAL_PATH: C:\Office_Automation\MEDI-IOT-EyeCare
- BRANCH: feat/clinical-query-quality-007
- HEAD_BEFORE: a8661d5ab665f686b2e81ef9c0be1e8f633c8e93
- HEAD_AFTER: a8661d5ab665f686b2e81ef9c0be1e8f633c8e93
- START_TIME_KST: 2026-10-23T00:35:41+09:00
- END_TIME_KST: 2026-10-23T00:49:50+09:00
- FILES_CHANGED: 이 문서, `models/clinical_support.py`, `services/clinical_queries.py`, `api/clinical_support.py`, `alembic/versions/medi008_clinical_query.py`
- TEST_RESULTS: 합성 SQLite 질의 수명주기 PASS. 일회용 PostgreSQL 15에서 동시 해결 1건 PASS 후 컨테이너 삭제
- REMAINING_ISSUES: 커밋과 push는 하지 않음. 화면과 잠금 업무는 없음

## 상태 전이

허용 전이는 다음뿐이다.

- `open` → `answered`
- `answered` → `resolved`
- `resolved` → `reopened`
- `reopened` → `answered`

그 외 전이는 거절한다. 각 전이와 배정은 `clinical_query_events`에 행위자, 시각, 사유를 남긴다. 응답 본문은 `clinical_query_responses`에 남긴다. 해결해도 이 행을 지우지 않는다.

배정 대상은 같은 연구의 사용자 또는 이미 있는 사이트 역할 중 하나다. 다른 사이트의 질의는 그 사이트 구성원만 읽고 바꾼다.

## 정정과의 연결

품질 소견으로 질의를 만들 수 있다. 정정은 `correct_observation`만 사용한다. 질의 상태는 정정만으로 바뀌지 않고, 검토자가 응답 또는 정정 결과를 본 뒤 `resolved` 또는 `reopened`로 옮긴다.
