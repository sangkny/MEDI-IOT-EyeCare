# 임상 지원 모듈 통합 계획

> 상태: 검사와 계획. 코드, 마이그레이션, 배포는 시작하지 않음.  
> 기준 커밋: `a5e2f71f98011ad52684bef62ded28432a5f8df0` (`main` = `origin/main`)  
> 로컬 클론: `C:\Office_Automation\MEDI-IOT-EyeCare`  
> 관찰 근거: SVG-SKLEE에서 읽기 전용으로 확인한 DeeVo Dr.Logs 메뉴 구조. 환자 행, 자격 증명, 내보내기 파일은 포함하지 않음.  
> 이 문서는 `PLATFORM-OVERVIEW.md`, `PROGNOSIS-MODEL-DESIGN.md`, `PROGNOSIS-TRACKING-DESIGN.md`, `SAMD-CHECKLIST.md`를 대체하지 않는다.

## 진행 기록

### 2026-10-26T17:46:02+09:00 — PC1-EYECARE-PHASE009-V110-FINAL-INTEGRATION-006

```
TASK_ID: PC1-EYECARE-PHASE009-V110-FINAL-INTEGRATION-006
EXECUTION_HOST: MEDIIOT-SKLEE
PC_ROLE: PC1
BRANCH: integration/eyecare-clinical-protocol-v110-009
WORKTREE: E:/Office_Automation/idea-collection/projects/_integration_eyecare_009v110
HEAD: b5b5f1ace304580bc977d8731a4d013b551552cf
MERGE_HEAD: 600ac7bd6f3dca5b7ef8cc998c621b43828a5f16
ANCESTRY: 600ac7b descends from 388a8ea and 8fba4bf. b5b5f1a does not.
START_TIME_KST: 2026-10-26T17:42:31+09:00
END_TIME_KST: 2026-10-26T17:46:02+09:00
ELAPSED: PT3M31S
SHARED_HEAD: 41642d0cb17d79f66fd0162d284a81003629551d
PREVIOUS_CANDIDATE: _integration_eyecare_009p remains uncommitted. HEAD b5b5f1a. MERGE_HEAD 388a8ea. Not aborted, reset, deleted, or pushed.
CONFLICTS: docs/CLINICAL-SUPPORT-INTEGRATION-PLAN.md 한 건. 기록을 시각 내림차순으로 유지.
TEST_TRANSFER: tests/test_clinical_data_lock.py 패치. tests/test_clinical_import.py는 3-way. v1.10 계획서 단언은 유지하고 PostgreSQL 대상자 범위만 이전.
PROTOCOL: medi-des-001-v1.10. 문서의 PROTOCOL_SHA256은 9e24fcedbd869e4e2b88d8b33e32acf617d4fd541199c78cd4c75d6444e2ac44. PDF는 복사하거나 열지 않음.
SQLITE: 79 passed, 4 skipped, exit 0, workers 0
POLICY: 8 passed, exit 0, workers 0
POSTGRESQL: pgvector/pgvector:pg15, tmpfs, 바인드 없음, 127.0.0.1:55441. head medi010. 원래 순서 4 passed. 역순 4 passed. 종료 코드 0. 컨테이너 eyecare-phase009-pg-v110 삭제. 55441은 배정이 아님.
GIT_ACTIONS: 커밋, 푸시, PR 없음
JUDGMENT: READY_FOR_COMMIT
PATENT: 이 PC1 통합에서 새 발명 후보 없음
```

### 2026-10-25T12:07:03+09:00 — Phase 009 게시

- TASK_ID: PC2-EYECARE-PHASE009-PUBLICATION-002
- EXECUTION_HOST: SVG-SKLEE
- BRANCH: feat/external-clinical-import-009
- HEAD_BEFORE: 1a92a4fae86598c903f4434f2b6a87ed0118b1cd
- CODE_COMMIT: f5ef3295662a23da99b42fc1aadcac5eec35c8fd
- START_TIME_KST: 2026-10-25T12:07:03+09:00
- END_TIME_KST: 2026-10-25T12:08:24+09:00
- ELAPSED: PT1M21S
- NEXT_APPROVAL: PC1 통합 브랜치와 Draft PR은 변경하지 않음. Phase 010은 시작하지 않음

### 2026-10-25T10:38:00+09:00 — Phase 009 R1 연결

- TASK_ID: PC2-EYECARE-PHASE009-LINKAGE-FIX-002
- EXECUTION_HOST: SVG-SKLEE
- BRANCH: feat/external-clinical-import-009
- HEAD: 1a92a4fae86598c903f4434f2b6a87ed0118b1cd
- START_TIME_KST: 2026-10-25T10:38:00+09:00
- END_TIME_KST: 2026-10-25T10:50:16+09:00
- ELAPSED: PT12M16S
- STATUS: VERIFIED_IN_ISOLATION, REQUIRES_CLINICAL_CONFIRMATION
- NEXT_APPROVAL: PC1 저장소와 통합 브랜치는 수정하지 않음. 커밋과 푸시 없음

### 2026-10-25T09:32:46+09:00 — Phase 009 게시

- TASK_ID: PC2-EYECARE-PHASE009-PUBLICATION-001
- EXECUTION_HOST: SVG-SKLEE
- PC_ROLE: PC2
- REPOSITORY: MEDI-IOT-EyeCare
- BRANCH: feat/external-clinical-import-009
- HEAD_BEFORE: 79848a924515ee72e8ed3f95af444a6aab60f750
- HEAD_AFTER: 이 게시 커밋
- START_TIME_KST: 2026-10-25T09:31:42+09:00
- END_TIME_KST: 2026-10-25T09:32:46+09:00
- ELAPSED: PT1M4S
- PUSH: origin `feat/external-clinical-import-009`만. PC1 통합 브랜치와 main은 변경하지 않음
- REMAINING_ISSUES: 실데이터 재실행은 하지 않음. A–E는 미해결 매핑 의존성
- NEXT_APPROVAL: Phase 010 착수 금지

### 2026-10-25T01:01:03+09:00 — Phase 009 로컬 가져오기

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
- FILES_CHANGED: EYECARE 가져오기 경로. DeeVo, PC1, 부모 서브모듈은 수정하지 않음
- TEST_RESULTS: 합성 SQLite exit 0. 일회용 PostgreSQL 15에서 `medi010_external_clinical_import`까지 upgrade 후 합성 1 passed. 실데이터 반영 DB는 삭제
- REMAINING_ISSUES: 워크북에 MEDI-DES-001 문자열이 없어 연구 귀속은 호출자가 지정. 커밋 없음
- NEXT_APPROVAL: 검토 후 커밋

### 2026-10-25T00:29:22+09:00 — PC1-EYECARE-PHASE008-PUBLICATION-002

```
TASK_ID: PC1-EYECARE-PHASE008-PUBLICATION-002
EXECUTION_HOST: MEDIIOT-SKLEE
PC_ROLE: PC1
REPOSITORY: MEDI-IOT-EyeCare
LOCAL_WORKTREE: E:/Office_Automation/idea-collection/projects/_integration_eyecare_008
BRANCH: integration/eyecare-clinical-data-lock-008
REMOTE: https-origin https://github.com/sangkny/MEDI-IOT-EyeCare.git
HEAD_BEFORE: 0d8aecd1527bb3f4bb32a648239b73f89f6f9463
SOURCE_SHA: 79848a924515ee72e8ed3f95af444a6aab60f750
MERGE_COMMIT: 0b6b30b1ccc315b4992eb85d43040fe8708561de
PARENTS: 0d8aecd1527bb3f4bb32a648239b73f89f6f9463 79848a924515ee72e8ed3f95af444a6aab60f750
START_TIME_KST: 2026-10-25T00:27:39+09:00
END_TIME_KST: 2026-10-25T00:29:22+09:00
ELAPSED: PT1M43S
PARENT_ARCHITECTURE_SHA: 633c7303edf8ac35a513c5a59b63185e8f336d76
SHARED_PR: https://github.com/sangkny/shared-libraries/pull/3
TEST_COMMAND: SHARED_LIBRARIES_PATH=_integration_shared_008. pytest policy and nine clinical files -q --tb=line
TEST_RESULTS: policy 8 passed, exit 0. SQLite 63 passed, 3 skipped, exit 0, aiosqlite workers 0
POSTGRESQL: not rerun. Evidence 2026-10-24T17:47:45+09:00 disposable pgvector/pgvector:pg15, medi009 head, 3 passed, exit 0, container removed
PUSH: https-origin new branch. Remote matches 0b6b30b before this documentation commit. No force
PR_URL: https://github.com/sangkny/MEDI-IOT-EyeCare/pull/3
PR_BASE: integration/eyecare-clinical-query-007
PR_STATE: Draft. Not merged. Draft PR 1 and 2 unchanged
FUTURE: EYECARE-CLINICAL-UX-001, EYECARE-CLINICAL-AI-QC-001, EYECARE-CLINICAL-IMPORT-001 remain unimplemented
RISK: test_lock_api_authorization 실패 경로는 비동기 엔진을 finally에서 닫지 않는다. 이번 통과 실행은 dispose 후 workers 0. 별도 테스트 유지 작업으로 남긴다
```

### 2026-10-24T17:47:45+09:00 — PC1-EYECARE-PHASE008-INTEGRATION-001

```
TASK_ID: PC1-EYECARE-PHASE008-INTEGRATION-001
EXECUTION_HOST: MEDIIOT-SKLEE
PC_ROLE: PC1
REPOSITORY: MEDI-IOT-EyeCare
LOCAL_WORKTREE: E:/Office_Automation/idea-collection/projects/_integration_eyecare_008
BRANCH: integration/eyecare-clinical-data-lock-008
HEAD: 0d8aecd1527bb3f4bb32a648239b73f89f6f9463
MERGE_HEAD: 79848a924515ee72e8ed3f95af444a6aab60f750
START_TIME_KST: 2026-10-24T17:43:11+09:00
END_TIME_KST: 2026-10-24T17:47:45+09:00
ELAPSED: PT4M34S
PARENT_ARCHITECTURE_SHA: 633c7303edf8ac35a513c5a59b63185e8f336d76
GIT_ACTIONS: --no-commit --no-ff. 커밋, 푸시, PR 없음
CONFLICTS: docs/CLINICAL-SUPPORT-INTEGRATION-PLAN.md 한 건. PC1과 PC2 기록을 시각 내림차순으로 유지
SHARED: 격리 후보 integration/clinical-data-lock-008. base dc68cb4, source 8a8b6a4. 충돌 없음. 커밋 없음
MIGRATION: 기존 개정은 수정하지 않음. medi009_clinical_data_lock down_revision은 medi008_clinical_query. 일회용 pgvector/pgvector:pg15, tmpfs, 바인드 없음, 127.0.0.1:55436. head medi009. 확인 후 컨테이너 삭제. 55436은 배정이 아님
TEST_COMMAND: SHARED_LIBRARIES_PATH=_integration_shared_008. pytest policy and nine clinical files -q --tb=line
TEST_RESULTS: 정책 8 passed, exit 0. SQLite 63 passed, 3 skipped, exit 0, aiosqlite workers 0. PostgreSQL 3 passed, exit 0, workers 0
OPEN_ISSUES: Draft PR 1과 2는 그대로. torch, cv2, 매니페스트 실패는 실행하지 않음. UX, AI QC, 외부 가져오기는 구현하지 않음. DeeVo에 접속하지 않음
```


### 2026-10-24T17:28:14+09:00 — Phase 008 명세 게시

- TASK_ID: PC2-EYECARE-PHASE008-PUBLICATION-001
- EXECUTION_HOST: SVG-SKLEE
- PC_ROLE: PC2
- REPOSITORY: MEDI-IOT-EyeCare
- LOCAL_PATH: C:\Office_Automation\MEDI-IOT-EyeCare
- BRANCH: feat/clinical-data-lock-008
- BASELINE_HEAD: 87aea032d7af8ec1723036a9ca7c1183dcdbd7a3
- HEAD_BEFORE: a8e32651c592cb30de27706c1d4c5c95c44c82c9
- HEAD_AFTER: 이 문서 커밋
- START_TIME_KST: 2026-10-24T17:27:38+09:00
- END_TIME_KST: 2026-10-24T17:28:14+09:00
- ELAPSED: PT36S
- FILES_CHANGED: 문서 4건. PC1 통합 브랜치, main, 부모 저장소는 수정하지 않음
- TEST_RESULTS: 이번 SQLite 재실행 42 passed, 3 skipped, exit 0. 정책 8 passed와 PostgreSQL 1 passed는 17:11 기록
- COMMIT: `docs: finalize Phase 008 clinical data lock specifications`
- PUSH: origin `feat/clinical-data-lock-008`만. force push 없음
- REMAINING_ISSUES: 이후 세 요구는 문서로만 유지. Phase 009는 시작하지 않음

### 2026-10-24T17:14:14+09:00 — Phase 008 식별자 구분

- TASK_ID: PC2-EYECARE-CLINICAL-SUPPORT-008
- EXECUTION_HOST: SVG-SKLEE
- PC_ROLE: PC2
- REPOSITORY: MEDI-IOT-EyeCare
- LOCAL_PATH: C:\Office_Automation\MEDI-IOT-EyeCare
- BRANCH: feat/clinical-data-lock-008
- HEAD_BEFORE: a8e32651c592cb30de27706c1d4c5c95c44c82c9
- HEAD_AFTER: a8e32651c592cb30de27706c1d4c5c95c44c82c9
- START_TIME_KST: 2026-10-24T17:12:00+09:00
- END_TIME_KST: 2026-10-24T17:14:14+09:00
- ELAPSED: PT2M14S
- MIGRATION: `medi009_clinical_data_lock`은 Alembic 개정명이다. Phase 008 완료에 이후 개발 단계 승인은 필요 없다
- REMAINING_ISSUES: DeeVo 가져오기, MEDI-DES-001 사례, 대상자·Visit 탐색, AI 보조 검증은 이후 요구로만 남김
- NEXT_APPROVAL: Phase 008 결과 검토 후 커밋. push는 그 승인 뒤

### 2026-10-24T17:11:37+09:00 — Phase 008 경계 재확인

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
- FILES_CHANGED: 통합 계획의 이 기록과 18절, 로드맵 13절, 잠금 명세, `EXTERNAL-CLINICAL-DATA-IMPORT-SPEC.md`
- TEST_RESULTS: SQLite 42 passed, 3 skipped, exit 0. 정책 8 passed, exit 0. 일회용 PostgreSQL 15 1 passed, exit 0 후 컨테이너 삭제
- REMAINING_ISSUES: 저장소는 분리 유지. DeeVo와 부모 서브모듈은 수정하지 않음. 문서 커밋과 push 없음
- NEXT_APPROVAL: 문서 변경의 별도 커밋 승인

### 2026-10-24T17:06:06+09:00 — PC1-EYECARE-PHASE007-PUBLICATION-007

```
TASK_ID: PC1-EYECARE-PHASE007-PUBLICATION-007
EXECUTION_HOST: MEDIIOT-SKLEE
PC_ROLE: PC1
REPOSITORY: MEDI-IOT-EyeCare
LOCAL_WORKTREE: E:/Office_Automation/idea-collection/projects/_integration_eyecare_007
BRANCH: integration/eyecare-clinical-query-007
REMOTE: https-origin https://github.com/sangkny/MEDI-IOT-EyeCare.git
HEAD_BEFORE: f637177647f7a1a8c941627e483f781e24d6dd83
TEST_CLEANUP_COMMIT: d906b6961256c41423d7144f0cfd04441dd5fb93
FILES: tests/test_clinical_api.py, tests/test_clinical_query_quality.py
ANCESTRY: 8d59f10477fc0002f6f5254d4e6b7e3b4012c3c7 and 87aea032d7af8ec1723036a9ca7c1183dcdbd7a3 remain parents of 7e1a194
START_TIME_KST: 2026-10-24T17:04:56+09:00
END_TIME_KST: 2026-10-24T17:06:06+09:00
ELAPSED: PT1M10S
PARENT_ARCHITECTURE_SHA: 633c7303edf8ac35a513c5a59b63185e8f336d76
TEST_COMMAND: SHARED_LIBRARIES_PATH=_integration_shared_007. pytest the eight clinical files -q --tb=line
TEST_RESULTS: 43 passed, 2 skipped, 1 warning. PYTEST_CODE 0. aiosqlite workers 0
POSTGRESQL: not rerun. Prior evidence 2026-10-23 disposable pgvector/pgvector:pg15, medi008 head, 2 passed, container removed
PUSH: remote matched f637177 and base remained 8d59f10. Normal fast-forward follows this documentation commit. No force
PR_URL: https://github.com/sangkny/MEDI-IOT-EyeCare/pull/2
PR_STATE: existing Draft. Not merged. Draft PR 1 unchanged
BLOCKERS: torch and cv2 collection failures and legacy manifest failures remain deferred
```

### 2026-10-24T16:45:06+09:00 — Phase 008 게시

- TASK_ID: PC2-EYECARE-PHASE008-PUBLISH-001
- EXECUTION_HOST: SVG-SKLEE
- PC_ROLE: PC2
- REPOSITORY: MEDI-IOT-EyeCare
- LOCAL_PATH: C:\Office_Automation\MEDI-IOT-EyeCare
- BRANCH: feat/clinical-data-lock-008
- HEAD_BEFORE: 87aea032d7af8ec1723036a9ca7c1183dcdbd7a3
- HEAD_AFTER: 이 게시 커밋
- START_TIME_KST: 2026-10-24T16:44:02+09:00
- END_TIME_KST: 2026-10-24T16:45:06+09:00
- ELAPSED: PT1M4S
- TEST_RESULTS: SQLite 42 passed, 3 skipped. 일회용 PostgreSQL 15 1 passed 후 삭제
- COMMIT: `feat: add clinical data locking audit and readiness`. shared-libraries는 `feat: add clinical locking authorization policies`
- PUSH: 두 저장소의 `feat/clinical-data-lock-008`만. PC1 통합 브랜치와 Draft PR은 변경하지 않음
- REMAINING_ISSUES: 필수 이후 기능 세 건은 구현하지 않음. Phase 009 미착수

### 2026-10-24T16:31:16+09:00 — PC1-EYECARE-TEST-CLEANUP-001

```
TASK_ID: PC1-EYECARE-TEST-CLEANUP-001
EXECUTION_HOST: MEDIIOT-SKLEE
PC_ROLE: PC1
REPOSITORY: MEDI-IOT-EyeCare
BRANCH: integration/eyecare-clinical-query-007
HEAD_BEFORE: f637177647f7a1a8c941627e483f781e24d6dd83
HEAD_AFTER: f637177647f7a1a8c941627e483f781e24d6dd83
START_TIME_KST: 2026-10-24T16:27:49+09:00
END_TIME_KST: 2026-10-24T16:31:16+09:00
ELAPSED: PT3M27S
FILES: tests/test_clinical_api.py, tests/test_clinical_query_quality.py
ROOT_CAUSE: sqlite+aiosqlite StaticPool 엔진을 dispose하지 않아 aiosqlite 0.22.1 비데몬 워커가 프로세스 종료를 막음
FIX: TestClient와 세션을 닫은 뒤 asyncio.run(engine.dispose())와 동기 engine.dispose()를 fixture 또는 try/finally에서 호출
TEST_A: tests/test_clinical_api.py 독립 프로세스. 4 passed. EXIT 0. aiosqlite 워커 0
TEST_B: tests/test_clinical_query_quality.py 독립 프로세스. 7 passed, 1 skipped. EXIT 0. aiosqlite 워커 0
TEST_C: 기존 8개 파일 독립 프로세스. 43 passed, 2 skipped. EXIT 0. aiosqlite 워커 0
PREVIOUS_COUNT: 43 passed, 2 skipped. 개수 변화 없음
CLASSIFICATION: TEST_ASSERTIONS_PASSED, PROCESS_EXIT_VERIFIED, RESOURCE_LEAK_RESOLVED
REMAINING: torch와 cv2 수집 실패, 매니페스트 기준 실패는 이번 범위 밖. 커밋하지 않음
```

### 2026-10-23T20:28:50+09:00 — Phase 008 PC2 잠금

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
- FILES_CHANGED: EYECARE 잠금·준비도 파일과 shared-libraries 정책 브랜치. 부모 서브모듈과 PC1 작업 트리는 수정하지 않음
- TEST_RESULTS: SQLite 20 passed, 1 skipped. 일회용 PostgreSQL 15 `pgvector/pgvector:pg15` `127.0.0.1:55434`에서 `medi009_clinical_data_lock`까지 upgrade 후 1 passed. 컨테이너와 데이터 디렉터리는 삭제
- MIGRATION: 운영 데이터베이스와 이름 있는 운영 볼륨은 사용하지 않음
- REMAINING_ISSUES: main 병합, 배포, DeeVo, 예측 학습은 하지 않음. 부모 기준 커밋 `633c7303edf8ac35a513c5a59b63185e8f336d76`의 포트와 인증 소유는 복제하지 않음
- NEXT_APPROVAL: 저장소별 커밋. Phase 009 착수 금지
### 2026-10-23T20:19:08+09:00 — PC1-PHASE007-PYTEST-EXIT-DIAGNOSIS

```
TASK_ID: PC1-PHASE007-PYTEST-EXIT-DIAGNOSIS
EXECUTION_HOST: MEDIIOT-SKLEE
PC_ROLE: PC1
REPOSITORY: MEDI-IOT-EyeCare
BRANCH: integration/eyecare-clinical-query-007
HEAD: f637177647f7a1a8c941627e483f781e24d6dd83
START_TIME_KST: 2026-10-23T20:13:20+09:00
END_TIME_KST: 2026-10-23T20:19:08+09:00
ELAPSED: PT5M48S
CLASSIFICATION: TEST_ASSERTIONS_PASSED, PROCESS_EXIT_BLOCKED, ROOT_CAUSE_IDENTIFIED
TEST_COMMAND: SHARED_LIBRARIES_PATH=_integration_shared_007. pytest tests/test_clinical_api.py tests/test_clinical_query_quality.py tests/test_observation_lifecycle.py tests/test_clinical_support_models.py tests/test_mvp04c_patient_crypto.py tests/test_mvp03a_qc_governance.py tests/test_dicom_foundation.py tests/test_mvp_result_contract.py -q --tb=line
ASSERTIONS: 43 passed, 2 skipped. pytest.main 반환 코드 0
PROCESS_EXIT: 정상 종료 아님. 22초 감시 후 종료 코드 1. 이전 강제 종료 코드 4294967295는 이 대기 중 프로세스를 끊은 값
ROOT_CAUSE: tests/test_clinical_api.py의 _app과 tests/test_clinical_query_quality.py의 test_query_api_requires_auth_and_filters가 sqlite+aiosqlite StaticPool 엔진을 dispose하지 않음. aiosqlite 0.22.1의 _connection_worker_thread는 daemon=False이며 tx.get에서 대기. CPython threading._shutdown이 비데몬 스레드를 기다림
CONTROLS: 동기 SQLite 6개 파일은 32 passed, 1 skipped 후 종료 코드 0. 빈 pytest는 플러그인 유무와 관계없이 종료 코드 0. clinical_api는 asyncio와 anyio 플러그인을 끄고도 4 passed 후 종료되지 않음. 앱 없는 최소 재현은 dispose 없으면 종료되지 않고 dispose 있으면 종료 코드 0
NOT_THE_CAUSE: 남은 asyncio 태스크 없음. 로깅 핸들러 없음. multiprocessing 자식 없음. FastAPI TestClient 포털 스레드는 세션 종료 뒤 남아 있지 않음. SQLAlchemy 동기 세션은 해당 파일에서 close됨
```

### 2026-10-23T19:59:59+09:00 — PC1-EYECARE-PHASE007-PUBLICATION-005

```
TASK_ID: PC1-EYECARE-PHASE007-PUBLICATION-005
EXECUTION_HOST: MEDIIOT-SKLEE
PC_ROLE: PC1
REPOSITORY: MEDI-IOT-EyeCare
LOCAL_WORKTREE: E:/Office_Automation/idea-collection/projects/_integration_eyecare_007
BRANCH: integration/eyecare-clinical-query-007
HEAD_BEFORE: 8d59f10477fc0002f6f5254d4e6b7e3b4012c3c7
SOURCE_SHA: 87aea032d7af8ec1723036a9ca7c1183dcdbd7a3
MERGE_COMMIT: 7e1a1949444dac57c660a09b8f5dab37d5822d55
START_TIME_KST: 2026-10-23T19:56:30+09:00
END_TIME_KST: 2026-10-23T19:59:59+09:00
ELAPSED: PT3M29S
PARENT_ARCHITECTURE_SHA: 633c7303edf8ac35a513c5a59b63185e8f336d76
PUSH_RESULT: https-origin fast-forward new branch. Remote matches 7e1a194. No force push
PR_URL: https://github.com/sangkny/MEDI-IOT-EyeCare/pull/2
PR_NUMBER: 2
PR_BASE: integration/eyecare-clinical-support
TEST_RESULTS: SHARED_LIBRARIES_PATH는 007 정책 작업 트리. SQLite 43 passed, 2 skipped. PostgreSQL 재실행 2 passed. medi008_clinical_query. torch와 cv2는 없음. 매니페스트 기준 실패는 재실행하지 않음. 새 회귀 없음
REMAINING: shared-libraries PR https://github.com/sangkny/shared-libraries/pull/2 가 먼저 필요하다. Draft PR 1과 이 PR은 머지하지 않음
```

### 2026-10-23T11:59:13+09:00 — PC1-EYECARE-PHASE007-INTEGRATION-004

```
TASK_ID: PC1-EYECARE-PHASE007-INTEGRATION-004
EXECUTION_HOST: MEDIIOT-SKLEE
PC_ROLE: PC1
REPOSITORY: MEDI-IOT-EyeCare
BRANCH: integration/eyecare-clinical-query-007
HEAD_BEFORE: 8d59f10477fc0002f6f5254d4e6b7e3b4012c3c7
HEAD_AFTER: 8d59f10477fc0002f6f5254d4e6b7e3b4012c3c7
MERGE_HEAD: 87aea032d7af8ec1723036a9ca7c1183dcdbd7a3
PARENT_ARCHITECTURE_SHA: 633c7303edf8ac35a513c5a59b63185e8f336d76
START_TIME_KST: 2026-10-23T11:50:42+09:00
END_TIME_KST: 2026-10-23T11:59:13+09:00
ELAPSED: PT8M31S
GIT_ACTIONS: 격리 워크트리 `_integration_eyecare_007`에서 `--no-commit --no-ff`. 커밋, 푸시, PR 없음
CONFLICTS: docs/CLINICAL-SUPPORT-INTEGRATION-PLAN.md, docs/PARENT-PLATFORM-ARCHITECTURE.md. 양쪽 기록을 시각 내림차순으로 유지
TEST_RESULTS: 정책 7 passed. SQLite 임상·보안 43 passed, PostgreSQL 전용 2 skipped. 질의 파일 재실행 7 passed. PostgreSQL 2 passed. 동시 정정은 원본 개정 1 값 5 유지, 후속 개정 2 값 6, 다른 트랜잭션 IntegrityError. torch와 cv2는 ModuleNotFoundError
MIGRATION: 컨테이너 eyecare-phase007-pg-004, 이미지 pgvector/pgvector:pg15, tmpfs, 바인드 없음, 호스트 127.0.0.1:55434. head medi008_clinical_query. 체인 medi004_billing -> medi006_clinical_support -> medi007_ecrf_foundation -> medi008_clinical_query. 확인 후 컨테이너 삭제. 55434는 배정이 아님
OPEN_ISSUES: 커밋 승인 전. 부모 shared-libraries main에는 007 권한이 없으므로 시험은 SHARED_LIBRARIES_PATH가 `_integration_shared_007`를 가리켜야 함. Phase 008 시작하지 않음
```

### 2026-10-23 09:15 KST — Phase 007 검증

- TASK_ID: PC2-CLINICAL-PHASE007-CHECKPOINT-001
- EXECUTION_HOST: SVG-SKLEE
- PC_ROLE: PC2
- REPOSITORY: MEDI-IOT-EyeCare
- LOCAL_PATH: C:\Office_Automation\MEDI-IOT-EyeCare
- BRANCH: feat/clinical-query-quality-007
- HEAD_BEFORE: a8661d5ab665f686b2e81ef9c0be1e8f633c8e93
- HEAD_AFTER: 이 검증 기록은 기능 커밋에 포함. 부모 아키텍처 문서는 별도 커밋
- START_TIME_KST: 2026-10-23T09:14:23+09:00
- END_TIME_KST: 2026-10-23T09:15:49+09:00
- FILES_CHANGED: 질의·품질 코드, `medi008_clinical_query`, 임상 문서. `docs/PARENT-PLATFORM-ARCHITECTURE.md` 제외
- TEST_RESULTS: SQLite 26 passed, 2 skipped. PostgreSQL 15에서 `medi008_clinical_query`까지 upgrade 후 2 passed. skipped는 passed로 세지 않음
- REMAINING_ISSUES: main 병합, 부모 서브모듈, PC1 Draft PR은 변경하지 않음

### 2026-10-23 00:35 KST — Phase 007 PC2 임상 질의

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
- FILES_CHANGED: EYECARE 임상 질의·품질 파일과 shared-libraries 정책 브랜치. PC1 작업 디렉터리는 수정하지 않음
- TEST_RESULTS: 합성 테스트 PASS. 일회용 PostgreSQL 15 PASS 후 삭제
- REMAINING_ISSUES: main 병합, 부모 서브모듈, push는 별도 승인. DeeVo는 접근하지 않음

### 2026-10-23 00:30 KST — 보안 강화와 임상 지원 통합 커밋

- 작업 ID: PC1-EYECARE-INTEGRATION-004
- EXECUTION_HOST: MEDIIOT-SKLEE
- PC_ROLE: PC1
- REPOSITORY: MEDI-IOT-EyeCare
- BRANCH: `integration/eyecare-clinical-support`
- HEAD_BEFORE: `bb984a820362bfd0fd191945a54bf3134e09aca1`
- HEAD_AFTER: `bb984a82`와 `a8661d5`의 병합 커밋. main에는 병합하지 않음
- START_TIME_KST: 2026-10-23 00:20
- END_TIME_KST: 2026-10-23 00:30
- TEST_RESULTS: `SHARED_LIBRARIES_PATH`로 통합 정책을 지정한 임상 API 4 passed. 관찰·모델·환자 암호화·QC·DICOM·MVP 계약 포함 39 passed, PostgreSQL 수명주기 1 passed
- 보존: Fernet 암호화, MVP 스크리닝, 임상 관찰, eCRF, 데이터 품질. PC1 `feature/mvp04c-security-hardening` 작업 트리와 stash는 변경하지 않음

### 2026-10-23 00:15 KST — PC1 보안 브랜치와 임상 브랜치 격리 병합 검증

- 작업 ID: PC1-EYECARE-INTEGRATION-003
- EXECUTION_HOST: MEDIIOT-SKLEE
- PC_ROLE: PC1
- 시작: 2026-10-23 00:03 KST
- 종료: 2026-10-23 00:15 KST
- REPOSITORY: MEDI-IOT-EyeCare
- LOCAL_PATH: `E:/Office_Automation/idea-collection/projects/_integration_eyecare`
- BRANCH: `integration/eyecare-clinical-support`
- HEAD_BEFORE: `bb984a820362bfd0fd191945a54bf3134e09aca1`
- HEAD_AFTER: 동일. 병합 커밋은 만들지 않음
- GIT_ACTIONS: `feature/mvp04c-security-hardening` 위에 `feat/clinical-support-002`를 `--no-commit --no-ff`로 병합. 충돌 0. Fernet 환자 암호화, MVP 스크리닝, 임상 API가 함께 남음
- TEST_RESULTS: 합성 SQLite 임상 API 4 passed. PostgreSQL 관찰 수명주기 1 passed. 롤백, eCRF 확정, 동시 정정 잠금, 오래된 개정 거부 확인. Alembic head `medi007_ecrf_foundation`
- OPEN_ISSUES: shared-libraries 정책은 별도 격리 브랜치에만 반영. 런타임은 `PYTHONPATH`로 그 워크트리를 사용. main 병합과 Phase 007은 시작하지 않음

### 2026-10-22 22:42 KST — PC2 기능 브랜치 게시

- 작업 ID: PC2-CLINICAL-GIT-PUBLISH-001
- 시작: 2026-10-22T22:42:55+09:00
- 종료: 2026-10-22T22:45:21+09:00
- PC: SVG-SKLEE / PC2
- MEDI-IOT-EyeCare: 브랜치 `feat/clinical-support-002`, 이전 HEAD `a5e2f71f98011ad52684bef62ded28432a5f8df0`, 작업 커밋 `3d8e5702e439db7cfd658e42b6977520845260a2`
- push: `origin` `feat/clinical-support-002` 신규 브랜치. main 병합과 force push 없음
- shared-libraries: 브랜치 `feat/medi-iot-clinical-policy`, 이전 HEAD `bd7d353f90328b8fecb31df897a8e74ecd5e0c43`, 커밋 `81a222baaa3ee256fe13fb33494ab2b6fd73ec76`. `origin`에 그 브랜치만 push. `main`은 `bd7d353` 유지
- 테스트: EYECARE 합성 19 passed, PostgreSQL 전용 1 skipped. 정책 테스트 6 passed
- 파일: EYECARE 임상 모델·서비스·API·medi006·medi007·문서·테스트 20개. shared-libraries는 `auth/policy.py`, `tests/test_policy.py`
- 남은 문제: main 미병합. 부모 서브모듈 포인터는 갱신하지 않음. MEDI-DES-001 필드는 계속 BLOCKED_PENDING_SOURCE
- 다음 승인: 각 기능 브랜치의 풀 리퀘스트와 main 병합

### 2026-10-22 22:13 KST — Phase 006 임상 API와 eCRF 기초

- 작업 ID: EYECARE-CLINICAL-SUPPORT-006
- 시작: 2026-10-22T22:13:52+09:00
- 종료: 2026-10-22T22:26:48+09:00
- PC: SVG-SKLEE
- 브랜치: `feat/clinical-support-002`
- HEAD: `a5e2f71f98011ad52684bef62ded28432a5f8df0` (커밋 전)
- 변경: `/api/v1/clinical-support` 인증 라우트, 설문 확정·정정, Visit-폼 배정, 품질 규칙 실행, `medi007` 초안. `record_observation`은 멤버십과 확정 검사를 통과한다
- 테스트: 합성 SQLite 19 passed. 일회용 PostgreSQL 15에서 마이그레이션, API 저장, 동시 정정, rollback PASS. 401·403·사이트 격리는 SQLite API 테스트
- 남은 문제: 핀 `5bc2147` 런타임 미실행. 임상 질의·잠금·예측 학습은 보류. MEDI-DES-001 필드는 BLOCKED_PENDING_SOURCE
- 다음 승인: EYECARE 커밋과 shared-libraries 정책 커밋을 따로 승인

### 2026-10-22 21:45 KST — Phase 005 부모 구조와 관찰 수명주기

- 작업 ID: EYECARE-CLINICAL-SUPPORT-005
- 시작: 2026-10-22T21:45:27+09:00
- 종료: 2026-10-22T21:55:58+09:00
- PC: SVG-SKLEE
- 브랜치: `feat/clinical-support-002`
- HEAD: `a5e2f71f98011ad52684bef62ded28432a5f8df0` (커밋 전)
- 변경: 초안 작성·수정, 명시적 확정, 사유 필수 정정, 유효 개정 조회, 이력 조회, PostgreSQL 행 잠금. `docs/PARENT-PLATFORM-ARCHITECTURE.md` 추가
- 테스트: 합성 SQLite 15 passed. 일회용 PostgreSQL 업그레이드와 수명주기 1 passed. 동시 정정은 성공 1건과 `ClinicalRecordError` 1건. HTTP는 추가하지 않음
- 남은 문제: PC1 UNKNOWN. shared-libraries 핀 미재현. `record_observation`은 004 즉시 확정 경로로 멤버십 검사가 없다
- 다음 승인: 아래 제안 커밋. 임상 HTTP는 shared-libraries 정책 변경 승인 후

### 2026-10-22 17:16 KST — Phase 004B 체크포인트

- 작업 ID: EYECARE-CLINICAL-SUPPORT-004B
- 시작: 2026-10-22T17:16:46+09:00
- 종료: 2026-10-22T17:19:41+09:00
- 경과: 2분 55초
- PC: SVG-SKLEE
- 브랜치: `feat/clinical-support-002`
- HEAD: `a5e2f71f98011ad52684bef62ded28432a5f8df0` (커밋 전)
- 테스트: 합성 SQLite 10 passed. 일회용 PostgreSQL에서 `alembic upgrade head`는 `saas` import 실패로 SQL 실행 전 중단. public 테이블 0개 확인 후 컨테이너 삭제
- 결정: 스키마는 변경하지 않음. 정정 사유 열과 동시 수정 잠금은 승인 전 보류
- 다음: 004 커밋 승인. Phase 005는 시작하지 않음

### 2026-10-22 14:45 KST — Phase 004 구현 진행

- 작업 ID: EYECARE-CLINICAL-SUPPORT-004
- 시작: 2026-10-22T14:45:25+09:00
- 종료: 2026-10-22T14:53:33+09:00
- 경과: 8분 8초
- PC: SVG-SKLEE
- 브랜치: `feat/clinical-support-002`
- HEAD: `a5e2f71f98011ad52684bef62ded28432a5f8df0` (커밋 전)
- 테스트: `tests/test_clinical_support_models.py` 10 passed. alembic upgrade 는 실행하지 않음
- 결정: 관찰 고유 키에 `revision`을 포함한다. DeeVo 쓰기는 SOURCE_SYSTEM_PROHIBITED. eCRF·질의·잠금 실행·가져오기·마이그레이션 적용은 CURRENT_PHASE_DEFERRED
- 다음: 사용자 커밋 승인. Phase 005는 시작하지 않음

### 2026-10-22 13:53 KST — Phase 003 구조 정리

- 시작 2026-10-22T13:50:18+09:00, 종료 2026-10-22T13:53:13+09:00, 경과 2분 55초, PC SVG-SKLEE
- 저장소 `MEDI-IOT-EyeCare`, 브랜치 `main`, HEAD `a5e2f71f98011ad52684bef62ded28432a5f8df0`. `origin/main`과 같음
- 부모 플랫폼 재사용 분류와 004 범위를 12장에 추가. 코드·테스트·마이그레이션 실행 없음
- 결정: 브랜치 이름 `feat/clinical-support-002` 유지. 레거시 인증 수정은 배포 게이트로 남김
- 미해결: MEDI-DES-001 프로토콜 필드 미확정
- 다음: Phase 004 승인 대기

### 2026-10-22 13:39 KST — Phase 002 설계

- 보안 조치, 데이터 모델, 품질 명세, 구현 로드맵을 작성. 구현과 push 없음

### 2026-10-22 13:24 KST — Phase 001 검사

- 로컬 클론과 임상 API·테이블 경계를 확인. 구현 없음

## 1. 저장소 동기화

SVG-SKLEE에서 `MEDI-IOT-EyeCare` 이름의 기존 클론은 없었다. 빈 경로 `C:\Office_Automation\MEDI-IOT-EyeCare`에 `main`을 새로 받았다. 받기 전 `git ls-remote`의 `HEAD`와 `refs/heads/main`은 위 SHA와 같았다. 기존 작업 트리를 덮어쓰지 않았고, pull, merge, rebase, push는 하지 않았다.

이 계획 문서를 추가하면 작업 트리는 더 이상 깨끗한 상태가 아니다. 커밋과 푸시는 별도 승인 전까지 하지 않는다.

## 2. 현재 구조

EyeCare는 안저 영상 진단과 환자·검사·진단 ORM을 가진 FastAPI 서비스다. 인증 라우터는 `api/auth.py`가 `shared-libraries`의 `auth.routes`를 다시 내보낸다. 역할 검사는 `require_role`, 기능 검사는 `policy_require`다. 이 저장소 안에는 `shared-libraries` 본체가 없다.

| 영역 | 있는 것 |
|------|---------|
| 환자·검사 | `models/medical.py`의 `Patient`, `EyeExam`, `Diagnosis`, `EyeImage` |
| 임상 연구 | `models/clinical.py`의 코호트, 이미지 멤버십, 진단 검토 큐 |
| API | `api/patients.py`, `api/clinical.py`, `api/dashboard.py`, `api/iot.py` |
| 예측 | 질환별 CNN 서비스, `services/prognosis_tracker.py` 스텁 |
| 감사 | 파트너 등록·분석 조회 `services/audit_log_service.py`, 온톨로지 `audit_trail` |
| 스키마 | Alembic 4개. 의료 테이블, 영상·지식, 임상 연구, 결제 |
| 내보내기 | FHIR 환자·관찰·진단 리포트, `services/report_gen.py` |

`clinical` 모델은 병원 EDC의 증례 관리가 아니라 공개·내부 데이터셋과 의사 검토 큐다. `EyeExam`은 검사일과 안압·시력을 저장한다. DeeVo에서 본 Visit 단계, 기간, 설문 연결, 환자 배정은 없다.

## 3. DeeVo 대비 기능 차이

분류는 저장소에 있는 코드와 읽기 전용 메뉴 관찰만 기준으로 한다. 버튼을 실행하지 않았으므로 저장, 삭제, 잠금, 내보내기의 서버 동작은 확인된 기능이 아니다.

| 기능 | 분류 | 근거 |
|------|------|------|
| 임상 데이터 관리 | EXISTING_BUT_INCOMPLETE | 환자·검사·영상·진단은 있다. 증례 트리, 저장 증례, 팔로우 증례, 공개 증례는 없다. |
| 설문 관리 | NEW_DEVELOPMENT_REQUIRED | 설문 모델, 버전, 제출, 작성 화면이 없다. |
| Visit·프로토콜 | EXISTING_BUT_INCOMPLETE | 검사일과 예후 스냅샷 SQL은 있다. Visit 단계·설문 바인딩·환자 배정은 없고, 스냅샷 테이블은 Alembic에 없다. |
| Data Quality Engine | NEW_DEVELOPMENT_REQUIRED | 필수값, 범위, 중복, 프로토콜 이탈을 판정하는 모듈이 없다. 온톨로지 게이트는 모델 출력 검사이며 입력 데이터 품질 엔진이 아니다. |
| 감사·출처 | EXISTING_BUT_INCOMPLETE | 파트너 감사 조회, 진단 검토, 추론 `audit_trail`은 있다. 트랜잭션 ID, 테이블, IP, 작업 내용, 잠금 이력, 감사 엑셀은 없다. |
| 임상 통계 | EXISTING_BUT_INCOMPLETE | 대시보드는 환자·검사 수, 진단 분포, 경고, LLM 사용량을 계산한다. 프로젝트·병원·치료 분포와 참여 인원 구성은 없다. |
| Predictive Analytics | REUSABLE_WITH_MODIFICATIONS | 안저 CNN과 종합 진단 API는 재사용할 수 있다. 예후 MLP는 진행 사례 부족으로 훈련이 보류되어 있다. |
| 보고·내보내기 | EXISTING_BUT_INCOMPLETE | 진단 문안과 FHIR 내보내기는 있다. 환자·AI·IoT·프로젝트 목록을 나누는 내보내기와 감사 내보내기는 없다. |

## 4. 제안하는 통합

별도 앱을 만들지 않고 `api/clinical.py`와 `models/clinical.py` 옆의 임상 지원 모듈로 둔다. 진단 CNN과 FHIR는 그대로 두고, EDC 기능은 새 테이블과 서비스로 분리한다.

```
기존 Patient / EyeExam / EyeImage / Diagnosis
        │
        ▼
ClinicalSubject ── Visit ── QuestionnaireResponse
        │            │
        │            └── DataQualityResult
        └── AuditEvent (append-only)
```

- `ClinicalSubject`는 `patients.id`를 참조한다. DeeVo 병록번호나 대상자 번호를 그대로 운영 식별자로 쓰지 않는다.
- `Visit`는 `EyeExam`을 대체하지 않는다. 검사 수치가 있으면 `eye_exams.id`를 선택적으로 연결한다.
- `Questionnaire`와 `QuestionnaireItem`은 버전을 고정한다. 제출은 항목 코드와 값만 저장한다.
- `DataQualityResult`는 제출 시점의 규칙 ID, 심각도, 통과 여부를 남긴다.
- `AuditEvent`는 변경 전후가 필요한 임상 쓰기와 내보내기 요청에만 추가한다. 기존 파트너 감사 조회를 임상 감사로 재사용하지 않는다.
- 예측은 기존 종합 진단과 `prognosis_tracker` 인터페이스를 호출하는 읽기 서비스로 연결한다. 예후 테이블은 진행 데이터가 생기기 전에는 마이그레이션하지 않는다.
- 개발 데이터베이스는 DeeVo 운영 데이터베이스에 연결하지 않는다.

## 5. Data Quality Engine

입력은 설문 제출, Visit 저장, 검사 수치다. 1차 구현은 결정적 규칙만 둔다.

| 규칙 | 예시 |
|------|------|
| 필수 | 프로토콜이 요구한 항목이 비어 있음 |
| 범위 | 안압, 시력, 날짜가 정의된 구간 밖 |
| 시점 | Visit 날짜가 이전 단계보다 앞섬 |
| 중복 | 같은 대상자, Visit, 설문 버전의 완료 제출이 이미 있음 |
| 잠금 | 잠긴 Visit에 대한 수정 |

결과는 `pass`, `warning`, `error`다. 모델 확률이나 온톨로지 승인 결과를 품질 판정에 섞지 않는다. 규칙 정의는 코드나 버전 있는 설정으로 두고, 환자 데이터와 함께 바꾸지 않는다.

## 6. Predictive Analytics 연결

재사용 경로는 기존 영상 분석과 종합 진단이다. 임상 지원 화면은 결과 ID와 모델 버전을 저장하고, 추론 서비스를 복제하지 않는다.

예후 예측은 `PROGNOSIS-MODEL-DESIGN.md`의 보류 결정을 유지한다. 방문 쌍의 진행 사례가 기준에 못 미치므로 임상 지원 모듈의 초기 범위는 저장된 추론 결과와 방문 간 변화 표시까지다. LSTM이나 Transformer 훈련은 이 계획의 구현 항목이 아니다.

## 7. 개발 순서

1. 승인 전: 이 문서 검토, 공개 저장소의 기본 비밀 처리 방침 결정.
2. 스키마 초안: Subject, Visit, Questionnaire, Quality, Audit. 예후 테이블은 제외.
3. 권한: 임상 읽기, 입력, 검토, 잠금, 내보내기를 기존 `policy_require`에 추가하는 설계.
4. 품질 규칙의 최소 집합과 테스트 데이터. 운영 환자 데이터는 사용하지 않는다.
5. 설문 작성·Visit 배정·감사 조회의 세로 흐름 하나.
6. 통계와 내보내기는 그 흐름이 잠금과 감사를 통과한 뒤 별도 승인.

대량 코드 변경, Alembic 적용, 배포는 각 단계의 승인 뒤에만 한다.

## 8. 보안과 개인정보

저장소는 공개다. `.gitignore`는 `.env`만 무시하고 `.env.local`과 `.env.test`는 추적된다.

| 파일 | 분류 | 위험 | 조치 |
|------|------|------|------|
| `config.py` | 기본 데이터베이스 URL에 사용자 이름과 비밀번호가 들어 있음 | 중간 | 비밀번호 없는 자리표시자로 바꾸고 환경 변수만 허용. 같은 값이 로컬 개발 밖 데이터베이스에 쓰였다면 교체 |
| `config.py` | 기본 JWT 서명 키가 코드에 있음 | 높음 | 기본값을 제거하고 미설정 시 기동 실패. 이 키로 발급된 토큰이 있으면 서명 키 교체 |
| `config.py` | 로컬 LLM 클라이언트 키 자리표시 | 낮음 | 운영 키로 쓰지 않기 |
| `.env.test` | 사설 IP의 LLM 주소가 커밋됨 | 중간 | 추적에서 제거하고 루프백 자리표시만 남김. 이력 재작성은 별도 승인 |
| `.env.local` | 상대 경로 모델 위치만 있음. 자격 증명 형태 없음 | 낮음 | 기기별 경로가 되면 추적 대상에서 제외 |

값은 이 문서에 적지 않는다. 파일을 삭제하거나 이력을 다시 쓰거나 자격 증명을 자동 교체하지 않는다.

추가로, `api/patients.py`와 `api/iot.py`의 등록·조회 경로는 이 저장소 기준으로 JWT 의존성이 붙어 있지 않다. 임상 지원 API는 첫 구현부터 `current_user_strict`와 기능 정책을 붙인다. DeeVo 세션이나 운영 데이터베이스는 개발 환경에 연결하지 않는다.

## 9. 확인된 API 경계

이 절은 2026-10-22 재검사에서 라우트와 모델을 다시 읽어 확정한 내용이다. 분류는 바꾸지 않는다.

| 경로 | 인증 | 저장 |
|------|------|------|
| `GET /clinical/studies`, 단건, 멤버십 목록, 검토 목록·단건 | `current_user_strict` | `clinical_studies`, `clinical_study_memberships`, `diagnosis_reviews` |
| `POST` 멤버십 | `policy_require("medi-iot", "create_exam")` | 같은 멤버십 테이블 |
| `POST /clinical/diagnoses/promote` | `promote_diagnosis` | `diagnoses`와 검토 큐 |
| `POST /clinical/reviews/{id}/decide` | `review_diagnosis` | 검토 상태 |
| `GET /clinical/fhir/...` | `current_user_strict` | 읽기 |
| `GET /dashboard/stats`, `/alerts`, `/llm-usage` | `dashboard_stats` | 집계 |
| `GET /dashboard/audit-logs` | `require_role("admin")` | 파트너 등록·분석만 조회 |
| `POST /diagnosis`, `/diagnosis/ai-analyze`, explain, comprehensive | `ai_analyze` | 진단 문안 |
| `POST /diagnosis/exam` | 의존성 없음 | `eye_exams` |
| `/patients` 등록·조회·목록·비활성화·검사·이력·추이·보고서 | 의존성 없음 | `patients`, `eye_exams`, `diagnoses` |
| `/iot` 장치 등록, 측정, HealthKit, Health Connect, 최신값, 웹소켓 | 의존성 없음 | 프로세스 메모리 `IoTGatewayService` |

환자 이름의 `name_encrypted` 컬럼은 등록 시 평문을 넣는다. 같은 함수에 AES-256은 운영 시점의 할 일로 남아 있다. `config.pii_encryption_enabled`는 이 쓰기 경로를 바꾸지 않는다.

Alembic에 있는 임상 테이블은 `patients`, `eye_exams`, `diagnoses`, `eye_images`, `clinical_studies`, `clinical_study_memberships`, `diagnosis_reviews`다. `gl_patients`와 `gl_visit_snapshots`는 `prognosis_tracker.py`의 SQL 문자열이며 마이그레이션이 없다. `database.create_tables()`의 개발용 `create_all`은 의료·지식 모델만 가져오고 임상 연구 모델을 가져오지 않는다.

검사 종류는 `fundus`, `oct`, `visual_field`, `slit_lamp`, `refraction`, `iop`다. 이 값은 Visit 프로토콜이 아니다.

## 10. 다음 승인

- 이 문서를 커밋할지 여부.
- 공개 저장소의 기본 비밀을 어떤 순서로 제거할지. 이력 재작성은 포함하지 않음.
- Subject, Visit, Questionnaire, Quality, Audit의 스키마 초안을 작성할지.
- 환자·IoT API의 인증 공백을 임상 모듈보다 먼저 막을지.

## 11. 002 설계 결정

2026-10-22에 구현 가능한 설계를 문서화했다. 코드, 마이그레이션, 배포, push는 하지 않았다. 이 절은 아래 문서를 복제하지 않는다.

- `docs/SECURITY-REMEDIATION-PLAN.md`
- `docs/CLINICAL-DATA-MODEL.md`
- `docs/DATA-QUALITY-ENGINE-SPEC.md`
- `docs/CLINICAL-MODULE-IMPLEMENTATION-ROADMAP.md`

EyeCare가 개발 본선이다. 임상 지원, 데이터 품질, 예측 결과 연결은 이 저장소에 둔다. SVG-Analyzer와 REA는 분석과 근거를 담당한다. 기존 진단과 데이터셋 API는 유지한다. DeeVo 운영 데이터는 연결하지 않는다.

제안 브랜치는 `feat/clinical-support-002`이며 아직 만들지 않았다. 기준 커밋은 `a5e2f71f98011ad52684bef62ded28432a5f8df0`이다.

## 12. Phase 003 부모 플랫폼 경계

2026-10-22에 `main.py`, `models/__init__.py`, `Dockerfile`, `static/`, compose 파일 위치를 다시 확인했다. 001·002의 임상 라우트 결론은 반복하지 않는다. 원격 `main`은 같은 SHA였다. 코드와 마이그레이션은 변경하지 않았다.

### 12.1 재사용 분류

| 영역 | 분류 | 근거 |
|------|------|------|
| 인증 | EXTEND | `api/auth.py`가 `shared-libraries` 라우트를 다시 내보낸다. 새 임상 API는 `current_user_strict`와 연구·사이트 정책을 붙인다. 인증 구현을 새로 만들지 않는다. |
| 사용자 관리 | REUSE_AS_IS | 이 저장소에 사용자 테이블이 없다. `StudySiteMember.user_id`는 외부 계정 ID 문자열이다. |
| 기관 관리 | NEW_COMPONENT | 기관 마스터가 없다. `StudySite`가 연구 경계다. `hospital_recommender`는 진료 의뢰용이며 사이트 마스터로 쓰지 않는다. |
| 환자 관리 | EXTEND | `Patient`를 유지한다. MVP에서 환자·진단 열은 바꾸지 않는다. `StudySubject.patient_id`만 선택적으로 연결한다. |
| 임상 검사 | EXTEND | `EyeExam`은 안저·OCT·시야·세극등·굴절·안압이다. TBUT·OSDI·Schirmer는 `ClinicalObservation`과 설문에 둔다. |
| 영상 | REUSE_AS_IS | `EyeImage`와 `static/fundus-lab`, `static/video-dr-lab`을 유지한다. |
| 진단 | REUSE_AS_IS | `Diagnosis`, `DiagnosisReview`, 종합 진단 서비스를 유지한다. Visit는 `diagnosis_id`만 참조한다. |
| AI 추론 | REUSE_AS_IS | 안저 CNN은 그대로 둔다. 시험 운영을 바꾸는 예측은 009의 NEW_COMPONENT다. |
| IoT | DEFERRED_REFACTOR | 측정은 프로세스 메모리에만 있다. eCRF 원본으로 연결하지 않는다. |
| 데이터베이스 | REUSE_AS_IS | PostgreSQL 비동기 세션과 Alembic. `main.py`는 `create_tables()` 직접 호출을 금지한다. |
| API 기반 | REUSE_AS_IS | FastAPI `/api/v1`, CORS, observability. 임상 라우트는 기존 `clinical` 라우터 아래에 둔다. |
| 보고 | EXTEND | 진단 문안과 FHIR는 유지한다. 연구 보고는 008의 새 기능이다. |
| 감사 | EXTEND | 파트너 감사 조회는 유지한다. 임상 감사는 `ClinicalAuditEvent`로 분리한다. |
| 배포 | DEFERRED_REFACTOR | `Dockerfile`은 있다. 앱 compose는 이 저장소에 없고 `training/docker-compose.train.yml`만 있다. 003·004에서 배포하지 않는다. |
| eCRF 화면 | NEW_COMPONENT | 연구용 프론트엔드가 없다. 006 이전에는 API와 합성 테스트만 둔다. |

### 12.2 모듈 경계

임상 연구 코드는 `models/clinical_support.py`, `schemas/clinical_support.py`, `services/clinical_records.py`, `services/data_quality.py`에 둔다. `diagnosis_pipeline`, `iot_gateway`, `report_gen`에 MEDI-DES-001 상수나 규칙을 넣지 않는다. 연구별 임계값은 `data_quality_rules.logic_json`에만 둔다.

새 임상 API는 인증과 사이트 구성원 검사가 있기 전에 노출하지 않는다. 기존 무인증 환자·IoT 라우트를 임상 데이터 입구로 쓰지 않는다. 그 결함의 수정은 `SECURITY-REMEDIATION-PLAN.md`에 남기고, 004의 모델 작업과 분리한다. 민감 임상 기능의 배포는 해당 보안 요구가 충족되기 전에 하지 않는다.

### 12.3 MEDI-DES-001

첫 연구 코드는 `MEDI-DES-001`이다. `study_kind`는 `prospective`다. 설계 속성은 탐색적, 전향적, 무작위, 이중눈가림, 샴 대조, 건성안이며 서비스 코드가 아니라 연구 설정 문서에 둔다.

로컬 작업 공간과 이 저장소에서 승인된 프로토콜 원문이나 비식별 내보내기 파일을 찾지 못했다. 방문 일수, 항목 코드, 순응도 필드는 미확정이다. 001에서 확인한 것은 프로젝트 선택 목록의 이름뿐이다. 필드 맵은 프로토콜이나 승인된 Sponsor 내보내기를 받은 뒤에 버전으로 고정한다.

치료군 배정은 `StudySubject`에 두지 않는다. 눈가림 역할이 승인되기 전에는 배정 파일을 가져오지 않는다. 운영 사용자가 배정을 추론하거나, 예측 결과가 진행 중 시험 수행을 바꾸게 하지 않는다.

DeeVo는 승인된 읽기 전용 원천이다. 003에서는 가져오기를 구현하지 않는다. 005의 경로는 원본 아카이브, SHA-256, 매니페스트, 스테이징, 필드 맵, 정규 임상 행, 파생 데이터, finding 순이다. 원본 값은 덮어쓰지 않고 DeeVo로 다시 쓰지 않는다. 개발 데이터베이스는 DeeVo 운영 데이터베이스와 분리한다.

### 12.4 004와의 차이

002 로드맵의 3번는 레거시 인증 수정이 스키마보다 앞이었다. 003은 그 결함을 취소하지 않는다. 플랫폼 전면 보안 리팩터는 004 범위가 아니고, 004는 모델·마이그레이션 초안·합성 테스트다. 배포 게이트는 보안 계획에 그대로 둔다. 브랜치 이름은 `feat/clinical-support-002`를 유지한다.

## 13. Phase 004 구현 상태

브랜치 `feat/clinical-support-002`를 `a5e2f71f98011ad52684bef62ded28432a5f8df0`에서 만들었다. 커밋과 push는 하지 않았다. `alembic upgrade`는 실행하지 않았다. DeeVo에는 접속하지 않았다.

EYECARE_IMPLEMENTED: `models/clinical_support.py`, `schemas/clinical_support.py`, `services/clinical_records.py`, `alembic/versions/medi006_clinical_support.py`, `ClinicalStudy.study_kind`, `protocol_version`.

EYECARE_VERIFIED: `tests/test_clinical_support_models.py` 10 passed. 호스트에는 `shared-libraries`가 없어 테스트가 `models/__init__.py`의 billing import를 피하고 서브모듈만 로드했다. 앱 런타임의 패키지 초기화는 이 테스트로 확인하지 않았다.

SOURCE_SYSTEM_PROHIBITED: DeeVo 운영 기록의 변경과 EYECARE에서 DeeVo로의 동기화.

CURRENT_PHASE_DEFERRED: eCRF 화면, ClinicalQuery 업무, 잠금·해제 업무, 가져오기·내보내기 실행, 치료군, 예측 학습, 마이그레이션 적용. 이 항목은 EYECARE_REQUIRED 로 남아 있다.

005는 시작하지 않는다. 프로토콜 필드와 마이그레이션 적용 승인이 없다.

## 14. Phase 004B 체크포인트

변경 파일은 004에서 만든 모델·스키마·서비스·테스트·`medi006`과 임상 문서 5개뿐이다. 환자 API, IoT, 이미지, 진단 라우트, `config.py`, `database.py`는 그대로다.

관찰 무결성:

- `record_status` 기본값은 `final`이다. `record_observation`도 항상 `final`을 쓴다. `draft`로 저장하는 서비스는 없다.
- 확정 행의 정정은 `revision + 1` 후속 행이다. 이전 행은 UPDATE 하지 않는다.
- 현재 유효 개정은 같은 측정 키에서 `revision`이 가장 큰 행이다. 이를 조회하는 전용 함수는 없다.
- 동시에 같은 행을 정정하면 고유 제약이 한쪽을 거절한다. `SELECT FOR UPDATE`는 없다.
- 행위자는 `recorded_by`와 감사 이벤트의 `actor_user_id`에 남는다. 정정 사유 인자와 사유 열은 없다. 감사 행은 본문 대신 해시만 저장하는 002 결정을 유지한다.
- 이 차이는 eCRF의 draft 저장과 사유 있는 정정에 필요하다. 스키마 변경은 승인 전에는 하지 않는다.

PostgreSQL: `127.0.0.1:55432`의 일회용 `pgvector/pgvector:pg16` 컨테이너만 사용했다. 기존 EYECARE 데이터베이스에는 접속하지 않았다. 개정 사슬은 `31f9f0473e87` → `c45bcf9c73f7` → `medi003_clinical_studies` → `medi004_billing` → `medi006_clinical_support` 하나다. `c45bcf9c73f7`는 pgvector가 필요하다. 공식 `alembic upgrade head`는 `alembic/env.py`가 `models`를 불러오며 `saas`가 없어 마이그레이션 SQL 전에 실패했다. 적용 결과는 없다.

shared-libraries: CI는 `https://github.com/sangkny/shared-libraries.git`를 depth 1로 클론하고 editable 설치한다. 이 저장소에 버전 핀은 없다. 앱 기동은 `saas`, `auth`, `llm`, `agents`, `ontology`가 있어야 한다. 설치와 클론은 하지 않았다.

Phase 005는 준비되지 않았다. 커밋, shared-libraries가 있는 환경에서의 `medi006` 적용 승인, 프로토콜 필드가 남아 있다.

## 15. Phase 005 결과

부모 구조는 `docs/PARENT-PLATFORM-ARCHITECTURE.md`에 적었다. 로컬 EYECARE HEAD `a5e2f71`과 부모 gitlink `1c8bd4a7`은 다르다. 포인터는 유지했다.

관찰 수명주기는 서비스 계층에 있다.

- `create_draft_observation`, `update_draft_observation`는 사이트 구성원만 초안을 만들고 고친다.
- `finalize_observation`는 값이 있는 초안만 `final`로 바꾸고 `finalized_by`, `finalized_at`을 남긴다.
- `correct_observation`와 `supersede_observation`는 비어 있지 않은 사유를 요구한다. 현재 유효 개정만 새 `revision`으로 남긴다. 이전 행의 값과 해시는 유지한다.
- `get_effective_observation`는 `record_status=final`인 최대 `revision`이다. 초안은 반환하지 않는다.
- PostgreSQL에서는 같은 측정 키를 `SELECT FOR UPDATE`로 잠근다. SQLite는 고유 제약이 같은 `revision` 중복을 거절한다.

임상 HTTP 라우트는 없다. shared-libraries 정책에 임상 액션이 없고, 무인증 레거시 라우트를 재사용하지 않았다.

일회용 PostgreSQL에서 개정 사슬이 `medi006_clinical_support`에 도달했다. 그 컨테이너는 삭제했다. 운영 데이터베이스에는 적용하지 않았다.

MEDI-DES-001은 전향, 무작위, 이중 눈가림, sham 대조, 안구건조 적응증의 첫 사용 사례다. 스크리닝, 등록, 대상자 코드, Visit, TBUT, Schirmer, OSDI, 순응, 이상반응, 프로토콜 이탈, 결측은 범위 이름이다. 승인 프로토콜이 없어 문항·창·임계값은 코드에 넣지 않았다. 치료군 배정은 `StudySubject` 밖에 둔다.

예측 모델은 학습하지 않았다. 품질 규칙은 실행하지 않았다. 이후 규칙은 유효 개정만 읽는다.

제안 커밋 메시지: `feat: 임상 관찰의 초안 확정 정정 수명주기를 추가한다`

제안 파일은 004의 모델·스키마·서비스·`medi006`·기존 임상 문서 5개에 `tests/test_observation_lifecycle.py`와 `docs/PARENT-PLATFORM-ARCHITECTURE.md`를 더한 목록이다. 커밋과 push는 하지 않았다.

Phase 006 제안: 이 파일 묶음의 커밋을 먼저 승인한다. 그 다음 shared-libraries에 임상 액션을 추가하는 별도 변경과, `current_user_strict`와 `StudySiteMember`를 함께 쓰는 라우트를 승인한다. 핀 `5bc2147`에서의 마이그레이션 재실행과 MEDI-DES-001 프로토콜 필드 확인이 그 뒤에 온다. 가져오기, 잠금 업무, 예측 학습은 그 승인에 포함하지 않는다.

## 16. Phase 006 결과

`/api/v1/clinical-support`가 연구, 사이트, 구성원, 대상자, Visit, 관찰 초안·확정·정정, 설문 정의·버전·응답을 제공한다. 라우트 설명은 `docs/CLINICAL-API.md`에 있다. 토큰과 정책, 사이트 멤버십이 모두 있어야 한다.

`record_observation`은 `create_draft_observation`과 `finalize_observation`을 호출한다. 멤버십이 없거나 값이 없으면 확정 행이 생기지 않는다.

eCRF 기초는 문항 JSON의 `type`, `required`, `min`, `max`와 Visit 코드에 폼을 연결하는 `visit_form_assignments`다. 설문 확정은 그 검증을 통과해야 한다. 정정은 이전 확정 응답을 남기고 초안 후속을 만든다. ClinicalQuery와 잠금 업무는 아직 없다.

MEDI-DES-001 템플릿 API는 `BLOCKED_PENDING_SOURCE`를 반환한다. 목표 등록 60명과 주 2회·8주라는 일반 설명만 담고, Visit 창과 문항과 배정은 비어 있다.

품질 규칙은 `logic_json`의 kind로 실행되고 관찰 값을 바꾸지 않는다. 예측 학습은 하지 않았다.

일회용 PostgreSQL 15.19에서 `medi007_ecrf_foundation`까지 적용했다. 컨테이너는 삭제했다.

제안 커밋은 저장소마다 따로다.

- MEDI-IOT-EyeCare: `feat: 인증된 임상 지원 API와 eCRF 기초를 추가한다`
- shared-libraries: `feat: medi-iot 정책에 임상 지원 액션을 추가한다` (`auth/policy.py`)

Phase 007 제안: 두 커밋을 승인한 뒤 임상 질의와 잠금의 최소 상태 모델을 구현한다. 프로토콜 원문이 오기 전에는 MEDI-DES-001 필드를 확정하지 않는다. 가져오기와 예측 학습은 그 단계에 넣지 않는다.

## 17. Phase 007 결과

PC1 통합을 기다리지 않고 `feat/clinical-support-002`의 `a8661d5`에서 `feat/clinical-query-quality-007`을 만들었다. PC1 작업 디렉터리와 DeeVo는 건드리지 않았다.

임상 질의는 `open → answered → resolved`와 `resolved → reopened → answered`만 허용한다. 품질 소견에서 질의를 만들 수 있고, 정정은 기존 개정 서비스만 사용한다. 해결은 관찰을 수정하지 않는다. 상세는 `docs/CLINICAL-QUERY-SPEC.md`에 있다.

품질 실행은 연구, 대상자, Visit, 폼 범위와 입력 직후 검증을 지원한다. 새 정책 액션은 shared-libraries 로컬 브랜치 `feat/clinical-query-quality-007`에 있다. 기준은 `81a222baaa3ee256fe13fb33494ab2b6fd73ec76`이며 아직 커밋하지 않았다.

일회용 PostgreSQL 15에서 `medi008_clinical_query`까지 upgrade 한 뒤 컨테이너를 삭제했다. 운영 데이터베이스에는 적용하지 않았다.

제안 커밋은 두 저장소로 나눈다. push와 main 병합, 부모 서브모듈 변경은 이 단계에 포함하지 않는다.

- MEDI-IOT-EyeCare `feat/clinical-query-quality-007`, 기준 `feat/clinical-support-002`: `feat: add clinical queries and repeatable quality checks`
- shared-libraries `feat/clinical-query-quality-007`, 기준 `feat/medi-iot-clinical-policy`: `feat: add clinical query and quality actions`

008에서는 데이터 잠금, 승인된 프로토콜 규칙, 두 브랜치의 검토와 부모 통합을 다룬다. 예측 학습과 스폰서 내보내기 가져오기는 각각 별도 승인이 있어야 한다.

## 18. Phase 008 결과와 이후 경계

PC2는 `feat/clinical-query-quality-007`의 `87aea032d7af8ec1723036a9ca7c1183dcdbd7a3`에서 `feat/clinical-data-lock-008`을 만들었다. PC1 통합 브랜치로 재기반하지 않았다. 부모 저장소, SVG-Analyzer, MEDI-SkinAI-Core, LookScan, DeeVo는 수정하지 않았다.

잠금 상태와 관찰 `record_status`는 분리돼 있다. 범위는 기록, Visit, 대상자, 연구다. 준비도는 Phase 007의 미해결 차단 질의와 품질 소견을 읽기만 한다. 질의 종료, 관찰 수정, 잠금 자동 변경은 없다. 승인된 프로토콜이 없으면 `BLOCKED_PENDING_PROTOCOL`이다. 애플리케이션 감사 해시는 규제 준수 증거가 아니다.

shared-libraries 변경은 `main`이 아닌 `feat/clinical-data-lock-008`의 `8a8b6a406cc22d120b8da49635efaec7ea826145`에 있다. 요청과 승인 액션은 분리돼 있고, Phase 006/007 임상 액션은 유지된다. 서비스는 사이트 구성원을 다시 검사한다.

Alembic 개정 `medi009_clinical_data_lock`은 Phase 008 스키마 순서다. 개발 단계 Phase 009가 아니다.

이후 요구 `EYECARE-CLINICAL-UX-001`, `EYECARE-CLINICAL-AI-QC-001`, `EYECARE-CLINICAL-IMPORT-001`은 로드맵 13절과 `EXTERNAL-CLINICAL-DATA-IMPORT-SPEC.md`에 범위, 의존성, 수용 기준으로 적혀 있다. 외부 DeeVo Excel 가져오기, MEDI-DES-001 사례, 대상자·Visit 탐색, AI 보조 검증은 이후 Phase 009 요구로만 둔다. Phase 008은 그 구현 없이 검증을 마친다.

## 19. Phase 009 가져오기

PC2는 `feat/clinical-data-lock-008`의 `79848a924515ee72e8ed3f95af444a6aab60f750`에서 `feat/external-clinical-import-009`를 만들었다. DeeVo에는 접속하지 않았다. 원본 반출은 `data/`에 있고 Git 무시 규칙 `data/`에 걸린다.

가져오기 핵심은 명세 시트와 데이터 시트 라벨이 일치할 때만 매핑한다. 제품별 시트 이름을 서비스에 고정하지 않는다. 확인은 초안만 만들고 잠그거나 확정하지 않는다. 같은 SHA-256은 다시 쓰지 않고, 값이 다른 개정은 불일치로 남긴다. 무작위 배정 값은 저장하지 않는다.

R1은 기본으로 꺼져 있다. 켠 경우에도 연구·사이트 멤버십을 통과한 호출만 확정할 수 있고, 다른 사이트의 기존 대상자는 `cross_site_subject`로 거절한다. 대상자 단위 양식은 정규 Visit를 만들지 않는다. 대상자·Visit 조회는 인증된 읽기 서비스만 있다. 대화형 대시보드와 AI 학습은 시작하지 않았다.
