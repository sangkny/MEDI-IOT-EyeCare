# 임상 지원 API

접두사는 `/api/v1/clinical-support`다. 모든 라우트는 Bearer 액세스 토큰과 `medi-iot` 정책 액션이 필요하다. 데이터 라우트는 추가로 연구 또는 사이트 구성원을 검사한다.

## 진행 기록

### 2026-10-24T16:45:06+09:00 — Phase 008 게시

- TASK_ID: PC2-EYECARE-PHASE008-PUBLISH-001
- EXECUTION_HOST: SVG-SKLEE
- BRANCH: feat/clinical-data-lock-008
- HEAD_BEFORE: 87aea032d7af8ec1723036a9ca7c1183dcdbd7a3
- HEAD_AFTER: 이 게시 커밋
- START_TIME_KST: 2026-10-24T16:44:02+09:00
- END_TIME_KST: 2026-10-24T16:45:06+09:00
- TEST_RESULTS: 잠금 API 포함 SQLite 42 passed, 3 skipped
- PUSH: origin `feat/clinical-data-lock-008`만

### 2026-10-23T20:28:50+09:00 — Phase 008 잠금 API

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
- FILES_CHANGED: `api/clinical_support.py`. 환자·IoT 라우트는 변경하지 않음
- TEST_RESULTS: 토큰 없음 401, staff 잠금 403, 비구성원 403, data_manager 잠금 200. SQLite 20 passed
- MIGRATION: API만. 스키마는 `medi009_clinical_data_lock`
- REMAINING_ISSUES: 정책 액션은 shared-libraries `feat/clinical-data-lock-008`에만 있음
- NEXT_APPROVAL: 두 저장소 커밋을 함께 검토

### 2026-10-23 09:15 KST — Phase 007 API 검증

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
- FILES_CHANGED: `api/clinical_support.py`
- TEST_RESULTS: 토큰 없음 401, staff 생성 403, 다른 사이트 403 PASS
- REMAINING_ISSUES: 정책 액션은 shared-libraries 별도 커밋

### 2026-10-23 00:35 KST — Phase 007 질의와 품질 API

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
- FILES_CHANGED: `api/clinical_support.py`, shared-libraries `auth/policy.py`
- TEST_RESULTS: 토큰 없음 401, staff 생성 403, 다른 사이트 의사 403 PASS
- REMAINING_ISSUES: 새 정책 액션은 로컬 브랜치 `feat/clinical-query-quality-007`에만 있다. 부모 핀에는 없다

### 2026-10-22 22:42 KST — PC2 기능 브랜치 게시

- 작업 ID: PC2-CLINICAL-GIT-PUBLISH-001
- 시작: 2026-10-22T22:42:55+09:00
- 종료: 2026-10-22T22:45:21+09:00
- PC: SVG-SKLEE / PC2
- 저장소: MEDI-IOT-EyeCare, 브랜치 `feat/clinical-support-002`, 이전 HEAD `a5e2f71f98011ad52684bef62ded28432a5f8df0`, 커밋 `3d8e5702e439db7cfd658e42b6977520845260a2`
- push: origin 기능 브랜치 생성. main 아님
- 테스트: 합성 API 포함 19 passed, 1 skipped
- 남은 문제: 정책 액션은 shared-libraries `81a222baaa3ee256fe13fb33494ab2b6fd73ec76`에 있으며 부모 핀에는 아직 없음
- 다음 승인: 두 브랜치를 함께 검토

### 2026-10-22 22:13 KST — Phase 006 API 명세

- 작업 ID: EYECARE-CLINICAL-SUPPORT-006
- 시작: 2026-10-22T22:13:52+09:00
- 종료: 2026-10-22T22:26:48+09:00
- PC: SVG-SKLEE
- 저장소: MEDI-IOT-EyeCare, 브랜치 `feat/clinical-support-002`, HEAD `a5e2f71f98011ad52684bef62ded28432a5f8df0`
- 변경: 이 문서와 `api/clinical_support.py`
- 테스트: 합성 SQLite에서 401, 403, 멤버 흐름, 사이트 격리, 초안·확정·정정, 설문 버전 PASS. 일회용 PostgreSQL 15에서 같은 관찰 흐름의 저장 PASS
- 남은 문제: 임상 질의와 잠금 라우트는 없다
- 다음 승인: shared-libraries 정책 커밋이 없으면 이 라우트의 정책 검사는 그 로컬 수정에 의존한다

## 라우트

| 메서드 | 경로 | 정책 액션 |
|--------|------|-----------|
| GET | `/templates/medi-des-001` | `clinical_study_read` |
| POST | `/studies` | `clinical_study_manage` |
| GET | `/studies`, `/studies/{id}`, `/studies/{id}/sites`, `/studies/{id}/members` | `clinical_study_read` |
| POST | `/studies/{id}/sites`, `/sites/{id}/members` | `clinical_study_manage` |
| POST | `/subjects` | `clinical_subject_manage` |
| GET | `/subjects/{id}`, `/studies/{id}/subjects` | `clinical_subject_read` |
| POST | `/visits` | `clinical_visit_manage` |
| GET | `/subjects/{id}/visits` | `clinical_visit_read` |
| POST | `/observations/drafts`, PATCH `/observations/{id}` | `clinical_observation_create` |
| POST | `/observations/{id}/finalize` | `clinical_observation_finalize` |
| POST | `/observations/{id}/corrections` | `clinical_observation_correct` |
| GET | `/observations/effective`, `/observations/history` | `clinical_observation_read` |
| POST | `/questionnaires`, `/questionnaires/{id}/versions`, `/visit-forms` | `clinical_questionnaire_manage` |
| POST | `/questionnaire-responses`, 항목, 확정, 정정 | `clinical_questionnaire_manage` |
| POST | `/studies/{id}/quality-runs` | `clinical_study_manage` |
| GET | `/studies/{id}/quality-findings` | `clinical_quality_read` |
| POST | `/studies/{id}/quality-validations`, `/visits/{id}/quality-runs` | `clinical_quality_execute` |
| GET | `/queries`, `/queries/{id}`, `/queries/{id}/history` | `clinical_query_read` |
| POST | `/queries`, `/findings/{id}/queries` | `clinical_query_create` |
| POST | `/queries/{id}/responses` | `clinical_query_respond` |
| POST | `/queries/{id}/assignments`, `/resolutions`, `/reopens` | `clinical_query_review` |
| POST | `/queries/{id}/corrections` | `clinical_observation_correct` |
| GET | `/readiness` | `clinical_readiness_read` |
| POST | `/locks/readiness` | `clinical_readiness_read` |
| POST | `/locks/requests` | `clinical_lock_request` |
| POST | `/locks/applications` | `clinical_lock_apply` |
| POST | `/locks/unlock-requests` | `clinical_unlock_request` |
| POST | `/locks/unlock-requests/{id}/approvals`, `/rejections` | `clinical_unlock_approve` |
| GET | `/locks/history` | `clinical_lock_read` |
| GET | `/audits` | `clinical_audit_read` |
| POST | `/studies/{id}/protocol-definitions`, `/protocol-definitions/{id}/approvals` | `clinical_protocol_manage` |
| POST | `/studies/{id}/monitoring-indicators` | `clinical_monitor_execute` |
| GET | `/studies/{id}/monitoring-indicators` | `clinical_monitor_read` |

토큰이 없으면 401이다. 정책이 거절하거나 사이트 구성원이 아니면 403이다. 대상이 없으면 404다. 빈 정정 사유, 값 없는 확정, 확정 행 수정은 400이다.

MEDI-DES-001 템플릿은 `status=BLOCKED_PENDING_SOURCE`이고 Visit 창과 설문 정의는 null이다. 배정 정보는 반환하지 않는다.
