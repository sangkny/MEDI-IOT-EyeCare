# 외부 임상 데이터 가져오기 명세

요구 ID는 `EYECARE-CLINICAL-IMPORT-001`이다. 이 문서는 이후 Phase 009 요구의 계약이다. Phase 008에서는 코드를 추가하지 않았고, 운영 파일을 가져오지 않았다. Alembic 개정 `medi009_clinical_data_lock`은 Phase 008 데이터베이스 순서이며 이 가져오기 기능이 아니다.

## 진행 기록

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
