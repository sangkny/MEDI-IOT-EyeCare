# 임상 데이터 잠금 명세

잠금 상태는 관찰의 `record_status`와 별도다. 공통 서비스는 특정 임상시험의 Visit 창, 문항, 임계값을 포함하지 않는다. 승인된 연구별 프로토콜이 없으면 준비도는 `BLOCKED_PENDING_PROTOCOL`이며 임상 검증 결과가 아니다.

스키마 개정 식별자는 `medi009_clinical_data_lock`이다. `medi008_clinical_query` 다음 Alembic 순서이며, 개발 단계 Phase 009가 아니다. Phase 008은 이 개정으로 스키마 작업을 마친다.

## 진행 기록

### 2026-10-24T17:28:14+09:00 — Phase 008 명세 게시

- TASK_ID: PC2-EYECARE-PHASE008-PUBLICATION-001
- EXECUTION_HOST: SVG-SKLEE
- PC_ROLE: PC2
- REPOSITORY: MEDI-IOT-EyeCare
- BRANCH: feat/clinical-data-lock-008
- BASELINE_HEAD: 87aea032d7af8ec1723036a9ca7c1183dcdbd7a3
- HEAD_BEFORE: a8e32651c592cb30de27706c1d4c5c95c44c82c9
- HEAD_AFTER: 이 문서 커밋
- START_TIME_KST: 2026-10-24T17:27:38+09:00
- END_TIME_KST: 2026-10-24T17:28:14+09:00
- ELAPSED: PT36S
- FILES_CHANGED: 문서 4건. 잠금 코드와 마이그레이션은 유지
- TEST_RESULTS: 이번 SQLite 재실행 42 passed, 3 skipped, exit 0. PostgreSQL 1 passed는 17:11 기록이며 이번 게시에 다시 실행하지 않음
- COMMIT: `docs: finalize Phase 008 clinical data lock specifications`
- PUSH: origin `feat/clinical-data-lock-008`만
- REMAINING_ISSUES: UX-001, AI-QC-001, IMPORT-001은 구현하지 않음

### 2026-10-24T17:14:14+09:00 — Alembic 식별자와 Phase 008 완료 구분

- TASK_ID: PC2-EYECARE-CLINICAL-SUPPORT-008
- EXECUTION_HOST: SVG-SKLEE
- PC_ROLE: PC2
- BRANCH: feat/clinical-data-lock-008
- HEAD_BEFORE: a8e32651c592cb30de27706c1d4c5c95c44c82c9
- HEAD_AFTER: a8e32651c592cb30de27706c1d4c5c95c44c82c9
- START_TIME_KST: 2026-10-24T17:12:00+09:00
- END_TIME_KST: 2026-10-24T17:14:14+09:00
- ELAPSED: PT2M14S
- MIGRATION: `medi009_clinical_data_lock`은 Phase 008의 Alembic 개정이다. 개발 단계 Phase 009가 아니다
- TEST_RESULTS: 코드 변경 없음. SQLite 재실행 42 passed, 3 skipped, exit 0
- REMAINING_ISSUES: 이후 기능은 문서로만 유지. 검토 전 커밋 없음
- NEXT_APPROVAL: Phase 008 결과 검토

### 2026-10-24T17:11:37+09:00 — 이후 기능 경계 확인

- TASK_ID: PC2-EYECARE-CLINICAL-SUPPORT-008
- EXECUTION_HOST: SVG-SKLEE
- PC_ROLE: PC2
- REPOSITORY: MEDI-IOT-EyeCare
- BRANCH: feat/clinical-data-lock-008
- HEAD_BEFORE: a8e32651c592cb30de27706c1d4c5c95c44c82c9
- HEAD_AFTER: a8e32651c592cb30de27706c1d4c5c95c44c82c9
- START_TIME_KST: 2026-10-24T17:08:00+09:00
- END_TIME_KST: 2026-10-24T17:11:37+09:00
- ELAPSED: PT3M37S
- FILES_CHANGED: 명세 경계만 추가. 잠금 코드는 유지
- TEST_RESULTS: SQLite 42 passed, 3 skipped, exit 0. 일회용 PostgreSQL 15에서 잠금 테스트 1 passed, exit 0 후 컨테이너 삭제
- REMAINING_ISSUES: UX-001, AI-QC-001, IMPORT-001은 구현하지 않음. 커밋하지 않음

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
- TEST_RESULTS: SQLite 42 passed, 3 skipped. PostgreSQL 15 일회용 `medi009_clinical_data_lock` 1 passed
- COMMIT: `feat: add clinical data locking audit and readiness`
- PUSH: origin `feat/clinical-data-lock-008`만
- REMAINING_ISSUES: EYECARE-CLINICAL-UX-001, EYECARE-CLINICAL-AI-QC-001, EYECARE-CLINICAL-IMPORT-001은 로드맵에 유지하고 구현하지 않음

### 2026-10-23T20:28:50+09:00 — Phase 008 잠금과 준비도

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
- FILES_CHANGED: 잠금·준비도 서비스, `medi009_clinical_data_lock`, 임상 API, 합성 테스트, 이 명세. shared-libraries 정책은 별도 브랜치
- TEST_RESULTS: SQLite 20 passed, PostgreSQL 전용 1 skipped. 일회용 PostgreSQL 15에서 `medi009_clinical_data_lock` upgrade와 잠금 테스트 1 passed 후 컨테이너 삭제
- MIGRATION: Alembic head `medi008_clinical_query` 다음 `medi009_clinical_data_lock`. 기존 마이그레이션은 수정하지 않음
- REMAINING_ISSUES: 커밋과 push 없음. 애플리케이션 해시는 규제 준수가 아님. 예측 모델은 시작하지 않음
- NEXT_APPROVAL: 저장소별 커밋. Phase 009는 별도 승인

## 상태 전이

```
DRAFT
  -> READY_FOR_REVIEW
  -> LOCKED
  -> UNLOCK_REQUESTED
  -> UNLOCKED
  -> READY_FOR_REVIEW
  -> LOCKED
```

해제 요청을 거절하면 `UNLOCK_REQUESTED -> LOCKED`다. 그 외 전이는 거부한다. 잠금을 반복 적용할 수 없다.

범위는 `record`(관찰 또는 설문 응답), `visit`, `subject`, `study`다. 현재 상태는 `data_lock_states` 한 행이고 버전으로 동시 갱신을 막는다. 이행은 `data_lock_records`에만 추가한다.

## 권한

플랫폼 정책과 사이트 역할을 둘 다 통과해야 한다. 서비스는 호출자가 넘긴 역할 문자열로 권한을 올리지 않는다.

| 동작 | 정책 액션 | 사이트 역할 |
|------|-----------|-------------|
| 준비도 조회 | `clinical_readiness_read` | 해당 사이트 또는 연구 구성원 |
| 잠금 요청 | `clinical_lock_request` | investigator, data_manager |
| 잠금 적용 | `clinical_lock_apply` | data_manager |
| 해제 요청 | `clinical_unlock_request` | investigator, data_manager |
| 해제 승인 또는 거절 | `clinical_unlock_approve` | data_manager 이면서 요청자가 아님 |
| 이력 조회 | `clinical_lock_read`, `clinical_audit_read` | 해당 사이트 구성원 |

연구 범위는 연구의 모든 사이트에서 같은 역할을 가진 구성원만 가능하다. 플랫폼 `admin`의 기존 와일드카드는 사이트 구성원 검사를 건너뛰지 않는다.

## 잠금 조건

적용 시점의 준비도가 `COMPLETE`이고 상태가 `READY_FOR_REVIEW`일 때만 `LOCKED`가 된다.

1. 승인된 프로토콜의 필수 기록과 설문이 있고, 필수 관찰이 확정돼 있다.
2. 미해결 차단 질의가 없다. 질의는 닫지 않는다.
3. 품질 실행이 끝났고 차단 소견이 열려 있지 않다. 소견은 자동으로 해결하지 않는다.
4. 행위자가 위 권한을 가진다.
5. 대상이 접근 가능한 연구와 사이트에 있다.
6. 같은 트랜잭션에서 감사 이벤트를 기록한다. 감사 기록에 실패하면 잠금 전이를 되돌린다.

잠금과 해제는 관찰 값, 해시, `record_status`를 바꾸지 않는다. `LOCKED`와 `UNLOCK_REQUESTED` 동안 관찰과 설문 수정은 거부한다.

## 준비도

상태는 다음 중 하나다.

- `COMPLETE`
- `INCOMPLETE`
- `BLOCKED_BY_QUERY`
- `BLOCKED_BY_QUALITY`
- `BLOCKED_PENDING_PROTOCOL`
- `LOCKED`

이미 잠긴 대상은 `LOCKED`다. 그 외에는 승인 프로토콜 없음, 차단 질의, 차단 소견 또는 미실행 품질, 결측 순서로 분류한다. `clinically_validated`는 항상 거짓이다. 승인 프로토콜이 있어도 `assessment_class`는 `OPERATIONAL_NOT_CLINICALLY_VALIDATED`다.

## 감사

임상 상태 전이는 `clinical_audit_events`에 추가한다. 행위자, 동작, 시각, 연구와 사이트, 대상, 이전 상태, 새 상태, 사유, 요청 식별자, 개정 번호를 남긴다. 해시는 정렬된 JSON의 SHA-256이다. 기존 행에 원문이 없으면 `LEGACY_HASH_ONLY`이며 일치로 간주하지 않는다. 이 해시는 규제 준수 증거가 아니다. PostgreSQL에서는 감사 행과 잠금 이력의 수정과 삭제를 트리거로 거부한다.

## AI 모니터링 경계

결정적 지표는 `monitoring_indicators`에만 쓴다. 원본 관찰, 질의, 소견을 바꾸지 않고 예측값을 만들지 않는다.

미래 인터페이스는 다음 순서다.

```
AI_MONITORING -> RISK_ASSESSMENT -> HUMAN_REVIEW -> CLINICAL_ACTION
```

`automatic_clinical_mutation`은 거짓이다. 알림이 임상 데이터를 자동으로 바꾸지 않는다. 프로토콜에 기준이 없으면 해당 신호는 `NOT_CONFIGURED` 또는 `BLOCKED_PENDING_PROTOCOL`이다. Visit 창과 종단 차이 한계는 연구 정의가 있을 때만 계산한다.

## 이후 기능과의 경계

다음 기능은 잠금 모델과 공존해야 하지만 Phase 008에서 구현하지 않는다.

- `EYECARE-CLINICAL-UX-001`은 잠금 상태와 준비도를 읽기 전용으로 보여 준다. 탐색 조회가 잠금을 우회하지 않는다.
- `EYECARE-CLINICAL-AI-QC-001`은 권고만 만든다. 정정은 기존 관찰 정정과 감사를 통과하고, 잠긴 대상에는 적용되지 않는다.
- `EYECARE-CLINICAL-IMPORT-001`은 가져온 기록을 초안과 확정 수명주기에 둔다. 가져오기가 잠금을 걸거나 기존 잠금 이력을 지우지 않는다. 상세는 `EXTERNAL-CLINICAL-DATA-IMPORT-SPEC.md`에 있다.

후보 순서는 승인된 단계 번호가 아니다.
