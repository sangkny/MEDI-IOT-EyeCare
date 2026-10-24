# 임상 모듈 구현 로드맵

> 작업: EYECARE-CLINICAL-SUPPORT-002. 이 문서는 구현 승인 전 순서다.  
> 기준 커밋: `a5e2f71f98011ad52684bef62ded28432a5f8df0`  
> 브랜치 제안: `feat/clinical-support-002`. 아직 만들지 않는다.  
> 상세는 `SECURITY-REMEDIATION-PLAN.md`, `CLINICAL-DATA-MODEL.md`, `DATA-QUALITY-ENGINE-SPEC.md`에 둔다.

## 진행 기록

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
- FILES_CHANGED: `docs/CLINICAL-MODULE-IMPLEMENTATION-ROADMAP.md`, `docs/CLINICAL-SUPPORT-INTEGRATION-PLAN.md`, `docs/CLINICAL-DATA-LOCK-SPEC.md`, `docs/EXTERNAL-CLINICAL-DATA-IMPORT-SPEC.md`. 임상 코드와 `medi009_clinical_data_lock`은 변경하지 않음
- TEST_RESULTS: 이번 SQLite 재실행 42 passed, 3 skipped, exit 0. shared-libraries 정책 8 passed와 일회용 PostgreSQL 15 잠금 1 passed, exit 0은 2026-10-24T17:11:37+09:00 기록이며 이번 게시에 다시 실행하지 않음
- COMMIT: `docs: finalize Phase 008 clinical data lock specifications`
- PUSH: origin `feat/clinical-data-lock-008`만. force push와 main 병합 없음
- REMAINING_ISSUES: EYECARE-CLINICAL-UX-001, EYECARE-CLINICAL-AI-QC-001, EYECARE-CLINICAL-IMPORT-001은 이후 요구로 유지. 구현하지 않음
- NEXT_APPROVAL: Phase 009 착수 금지

### 2026-10-24T17:14:14+09:00 — Phase 008 마이그레이션 식별자 확인

- TASK_ID: PC2-EYECARE-CLINICAL-SUPPORT-008
- EXECUTION_HOST: SVG-SKLEE
- PC_ROLE: PC2
- REPOSITORY: MEDI-IOT-EyeCare
- LOCAL_PATH: C:\Office_Automation\MEDI-IOT-EyeCare
- BRANCH: feat/clinical-data-lock-008
- BASELINE_HEAD: 87aea032d7af8ec1723036a9ca7c1183dcdbd7a3
- HEAD_BEFORE: a8e32651c592cb30de27706c1d4c5c95c44c82c9
- HEAD_AFTER: a8e32651c592cb30de27706c1d4c5c95c44c82c9
- START_TIME_KST: 2026-10-24T17:12:00+09:00
- END_TIME_KST: 2026-10-24T17:14:14+09:00
- ELAPSED: PT2M14S
- FILES_CHANGED: 로드맵, 통합 계획, 잠금 명세, 가져오기 명세의 식별자 설명. 잠금 코드와 Alembic 개정 파일은 유지
- MIGRATION: `medi009_clinical_data_lock`은 `medi008_clinical_query` 다음 Alembic 개정이다. 개발 단계 Phase 009가 아니다. Phase 008을 끝내는 데 이후 단계 승인은 필요 없다
- TEST_RESULTS: 코드 변경 없음. 이번 SQLite 재실행 42 passed, 3 skipped, exit 0. 정책 8 passed와 일회용 PostgreSQL 15 잠금 1 passed는 17:11 검증, exit 0
- REMAINING_ISSUES: UX-001, AI-QC-001, IMPORT-001은 이후 요구 문서로만 남긴다. 구현하지 않음. 검토 전 커밋과 push 없음
- NEXT_APPROVAL: Phase 008 결과 검토 후 커밋

### 2026-10-24T17:11:37+09:00 — Phase 008 재검증과 이후 요구 명세

- TASK_ID: PC2-EYECARE-CLINICAL-SUPPORT-008
- EXECUTION_HOST: SVG-SKLEE
- PC_ROLE: PC2
- REPOSITORY: MEDI-IOT-EyeCare
- LOCAL_PATH: C:\Office_Automation\MEDI-IOT-EyeCare
- BRANCH: feat/clinical-data-lock-008
- BASELINE_HEAD: 87aea032d7af8ec1723036a9ca7c1183dcdbd7a3
- HEAD_BEFORE: a8e32651c592cb30de27706c1d4c5c95c44c82c9
- HEAD_AFTER: a8e32651c592cb30de27706c1d4c5c95c44c82c9
- START_TIME_KST: 2026-10-24T17:08:00+09:00
- END_TIME_KST: 2026-10-24T17:11:37+09:00
- ELAPSED: PT3M37S
- FILES_CHANGED: 이 로드맵, 통합 계획, 잠금 명세, `docs/EXTERNAL-CLINICAL-DATA-IMPORT-SPEC.md`. 잠금 코드와 마이그레이션은 바꾸지 않음
- WORKING_TREE: 문서 4건만 미커밋. 환자 데이터와 자격 증명 없음
- TEST_RESULTS: SQLite 42 passed, 3 skipped, exit 0. shared-libraries 정책 8 passed, exit 0. 일회용 PostgreSQL 15 `127.0.0.1:55436`에서 `medi009_clinical_data_lock`까지 upgrade 후 잠금 테스트 1 passed, exit 0. 컨테이너 삭제
- MIGRATION: 추가 개정 없음. 기존 head `medi009_clinical_data_lock`
- VERIFIED: 잠금, 해제, 준비도, 감사, 인증 API, 합성 SQLite, 정책
- SKIPPED_OR_UNCHANGED: UX-001, AI-QC-001, IMPORT-001 구현. DeeVo, 운영 가져오기, 모델 학습, main 병합, push
- REMAINING_ISSUES: 세 필수 기능은 명세만 있다. 이 문서 변경은 커밋하지 않음
- NEXT_APPROVAL: Phase 008 결과 검토 후 커밋. 이후 기능 구현은 이 승인과 별도다

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
- FILES_CHANGED: Phase 008 잠금·감사·준비도 구현과 이 로드맵. 무관한 파일은 제외
- TEST_RESULTS: SQLite 42 passed, 3 skipped. 일회용 PostgreSQL 15에서 `medi009_clinical_data_lock` upgrade와 잠금 테스트 1 passed 후 컨테이너 삭제. shared-libraries 정책 8 passed
- COMMIT: `feat: add clinical data locking audit and readiness`
- PUSH: origin `feat/clinical-data-lock-008`만. main 병합과 force push 없음
- REMAINING_ISSUES: UX, AI 재확인, 외부 가져오기는 아래 필수 기능으로 남김. Phase 009는 시작하지 않음
- NEXT_APPROVAL: 기능 브랜치 검토

### 2026-10-23T20:28:50+09:00 — Phase 008 데이터 잠금

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
- FILES_CHANGED: 잠금 수명주기, 준비도, 감사 확장, `medi009_clinical_data_lock`, 합성 테스트, 임상 문서
- TEST_RESULTS: SQLite 20 passed. 일회용 PostgreSQL 15에서 upgrade head `medi009_clinical_data_lock`과 잠금 테스트 1 passed. 컨테이너 삭제
- MIGRATION: `medi009_clinical_data_lock`. 이전 개정은 유지
- REMAINING_ISSUES: 커밋 전. Phase 009 미착수. 예측 학습 없음
- NEXT_APPROVAL: EYECARE와 shared-libraries를 각각 커밋

### 2026-10-23 09:15 KST — Phase 007 체크포인트

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
- FILES_CHANGED: Phase 007 구현과 임상 문서. 부모 아키텍처 문서는 제외
- TEST_RESULTS: SQLite 26 passed, 2 skipped. PostgreSQL 2 passed
- REMAINING_ISSUES: Phase 008은 시작하지 않음

### 2026-10-23 00:35 KST — Phase 007 수행

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
- FILES_CHANGED: 질의 서비스, 품질 엔진, medi008, 합성 테스트, 이 로드맵
- TEST_RESULTS: 합성 SQLite 26 passed, PostgreSQL 전용 2 skipped. 일회용 PostgreSQL 15 질의 테스트는 그 전에 1 passed
- REMAINING_ISSUES: 008에서 잠금, 승인된 프로토콜 규칙, 부모 통합을 다룬다. 이 브랜치는 커밋하지 않음

### 2026-10-22 22:42 KST — PC2 기능 브랜치 게시

- 작업 ID: PC2-CLINICAL-GIT-PUBLISH-001
- 시작: 2026-10-22T22:42:55+09:00
- 종료: 2026-10-22T22:45:21+09:00
- PC: SVG-SKLEE / PC2
- 저장소: MEDI-IOT-EyeCare `feat/clinical-support-002` `3d8e5702e439db7cfd658e42b6977520845260a2`. shared-libraries `feat/medi-iot-clinical-policy` `81a222baaa3ee256fe13fb33494ab2b6fd73ec76`
- push: 각 origin 기능 브랜치만. main 병합 없음
- 테스트: 합성 19 passed, 정책 6 passed
- 남은 문제: main 미반영. Phase 007 미착수
- 다음 승인: 풀 리퀘스트

### 2026-10-22 22:13 KST — Phase 006 수행

- 작업 ID: EYECARE-CLINICAL-SUPPORT-006
- 시작: 2026-10-22T22:13:52+09:00
- 종료: 2026-10-22T22:26:48+09:00
- PC: SVG-SKLEE, 브랜치 `feat/clinical-support-002`, HEAD `a5e2f71f98011ad52684bef62ded28432a5f8df0`
- 변경: 인증된 임상 API, eCRF 기초, 품질 규칙 실행, PostgreSQL 15 일회용 검증
- 테스트: SQLite 19 passed. PostgreSQL 15 마이그레이션·API 저장·동시 정정·rollback PASS
- 남은 문제: 커밋 전. 질의·잠금·가져오기·예측은 보류
- 다음 승인: 저장소별 커밋. Phase 007 착수

### 2026-10-22 21:45 KST — Phase 005 수행

- 작업 ID: EYECARE-CLINICAL-SUPPORT-005
- 시작: 2026-10-22T21:45:27+09:00
- 종료: 2026-10-22T21:55:58+09:00
- PC: SVG-SKLEE, 브랜치 `feat/clinical-support-002`, HEAD `a5e2f71f98011ad52684bef62ded28432a5f8df0`
- 변경: 부모 구조 확인, 관찰 수명주기 서비스, 일회용 PostgreSQL에서 `medi006` 적용 확인. 가져오기와 예측 학습은 하지 않음
- 테스트: SQLite 15 passed. 일회용 PostgreSQL 수명주기 passed. 임상 HTTP 없음
- 남은 문제: 커밋 전. PC1 UNKNOWN. 정책 액션 없음
- 다음 승인: Phase 006 전 커밋과 shared-libraries 정책 변경

### 2026-10-22 17:16 KST — Phase 004B 단계 확인

- 작업 ID: EYECARE-CLINICAL-SUPPORT-004B
- 시작: 2026-10-22T17:16:46+09:00
- 종료: 2026-10-22T17:19:41+09:00
- 경과: 2분 55초
- PC: SVG-SKLEE, 브랜치 `feat/clinical-support-002`, HEAD `a5e2f71f98011ad52684bef62ded28432a5f8df0`
- 테스트: 합성 SQLite 10 passed. 일회용 PostgreSQL 마이그레이션은 import 단계에서 실패
- 다음: 005 미착수

### 2026-10-22 14:45 KST — Phase 004 구현

- 작업 ID: EYECARE-CLINICAL-SUPPORT-004
- 시작: 2026-10-22T14:45:25+09:00
- 종료: 2026-10-22T14:53:33+09:00
- 경과: 8분 8초
- PC: SVG-SKLEE, 브랜치 `feat/clinical-support-002`, HEAD `a5e2f71f98011ad52684bef62ded28432a5f8df0` (커밋 전)
- 테스트: 합성 SQLite 10 passed. 마이그레이션 미적용
- 결정: 고유 키에 `revision` 추가. 최종 기능은 유지하고 이번 단계 실행만 미룸
- 다음: 커밋 승인 후 005는 별도 승인

### 2026-10-22 13:53 KST — Phase 003 단계 경계

- 시작 2026-10-22T13:50:18+09:00, 종료 2026-10-22T13:53:13+09:00, 경과 2분 55초, PC SVG-SKLEE
- HEAD `a5e2f71f98011ad52684bef62ded28432a5f8df0`, 브랜치 `main`. 제안 브랜치 `feat/clinical-support-002`는 아직 없음
- 004 파일 목록을 7장에 고정. 구현과 테스트 실행 없음
- 다음: 004 착수 승인

### 2026-10-22 13:39 KST — Phase 002 로드맵

- 보안 선행과 `medi006` 초안 순서를 기록. 003이 인증 결함을 취소하지 않고 004 범위만 좁힘

## 1. 결정

EyeCare 저장소가 개발 본선이다. SVG-Analyzer와 REA는 분석과 근거를 담당한다. 임상 지원, 데이터 품질, 예측 결과 연결은 EyeCare 안에서 구현한다. 기존 진단, 연구 데이터셋, FHIR, 결제는 유지한다. DeeVo 운영 접근은 읽기 전용이며, 이 로드맵의 구현 단계에서도 연결하지 않는다.

## 2. 바꿀 파일

### 보안 단계

| 파일 | 변경 |
|------|------|
| `api/patients.py` | 인증과 `patient_read` / `patient_write` |
| `api/diagnosis.py` | `POST /exam`에만 인증과 `patient_write` |
| `api/iot.py` | `iot_read` / `iot_ingest` |
| `api/images.py` | `image_read` / `image_write` |
| `config.py` | JWT 키와 데이터베이스 URL 기본 비밀 제거 |
| `.gitignore` | `.env.local`, `.env.test` 무시 |
| `tests/test_e2e.py` | 인증 픽스처 |
| `tests/test_e2e_context.py` | 같은 수정 |
| `tests/test_e2e_week4_full_flow.py` | 같은 수정 |
| `tests/test_patient_history.py` | 같은 수정 |
| `tests/test_images.py` | 같은 수정 |

저장소 밖: `shared-libraries`의 `medi-iot` 정책 목록.

추적 해제 대상: `.env.test`, `.env.local`. 이력 재작성은 포함하지 않는다.

### 스키마와 모듈 단계

| 파일 | 변경 |
|------|------|
| `models/clinical.py` | `ClinicalStudy.study_kind`, `protocol_version` |
| 새 `models/clinical_support.py` | 사이트, 대상자, Visit, 창, 설문, 관찰, 규칙, finding, 감사, 잠금, 내보내기 |
| 새 `schemas/clinical_support.py` | 요청과 응답 |
| 새 `api/clinical_support.py` | `/clinical/support` |
| `api/clinical.py` | 새 라우터 include. 기존 연구 라우트는 유지 |
| `api/__init__.py` | 변경 없음. 기존 clinical prefix를 유지 |
| `database.py` | `create_all` import에 임상 모델 추가. 운영 스키마 생성 경로로는 쓰지 않음 |
| 새 `services/data_quality.py` | 명세의 판정 |
| 새 `services/clinical_audit.py` | 감사 추가 |
| 새 `alembic/versions/medi006_clinical_support.py` | 승인 뒤에만 작성 |
| 새 `tests/test_clinical_support_auth.py` | 사이트 경계 |
| 새 `tests/test_data_quality_engine.py` | 합성 픽스처와 해시 불변 |

기존 Alembic 4개와 `services/prognosis_tracker.py`의 SQL 문자열은 수정하지 않는다. 예후 테이블은 이번 마이그레이션에 넣지 않는다.

## 3. 예상 마이그레이션

실행하지 않는다. 개발 데이터베이스에 적용하는 것도 승인 전이다.

1. 보안 단계에는 스키마 마이그레이션이 없다.
2. `medi006_clinical_support`는 새 테이블을 만들고 `clinical_studies`에 `study_kind`, `protocol_version`만 추가한다. `study_kind` 기본값은 `dataset`이다.
3. `patients`, `eye_exams`, `diagnoses`, `eye_images`, `diagnosis_reviews`, 멤버십 테이블은 열을 삭제하거나 의미를 바꾸지 않는다.
4. 이름 암호문 접두의 일괄 변환은 마이그레이션에 넣지 않는다.
5. 운영 적용과 배포는 이 로드맵 밖에 둔다.

## 4. 호환과 무결성

- 토큰 없는 기존 테스트와 클라이언트는 401이 된다.
- 기본 비밀을 쓰던 로컬 기동은 환경 변수가 없으면 멈춘다.
- 평문 이름을 암호문으로 일괄 바꾸면 기존 표시가 깨진다. 읽기는 접두로 구분한다.
- 데이터셋 연구에 전향 프로토콜 규칙을 적용하면 Messidor 경로가 실패한다. `study_kind=dataset`은 품질 집합에서 제외한다.
- `create_all`이 새 모델을 가져오기 전에 개발 기동이 테이블 없음을 만날 수 있다. 스키마 생성은 Alembic만 사용한다.
- 품질 엔진이 관찰을 UPDATE하면 불변 조건이 깨진다. 테스트는 `row_hash`로 막는다.
- 잠금 전의 draft 설문만 수정한다. 완료 응답의 수정은 새 행이다.
- 예측 결과는 `diagnoses` 또는 `derived` 관찰에 두고 원본 TBUT와 Schirmer를 덮어쓰지 않는다.

## 5. 구현 순서

1. 이 문서 묶음의 승인.
2. `feat/clinical-support-002`를 `a5e2f71f98011ad52684bef62ded28432a5f8df0`에서 만든다.
3. 인증, 정책, 설정 기본값, 테스트 픽스처. 스키마 변경 없음.
4. 합성 데이터로 보안 회귀를 통과시킨다.
5. `medi006` 초안과 모델을 개발 데이터베이스에만 적용하는 별도 승인.
6. support API의 연구·사이트·대상자·Visit·설문·관찰.
7. 품질 엔진과 불변 테스트. OSDI, TBUT, Schirmer 순서로 규칙을 켠다.
8. 잠금, 감사, 내보내기 기록. 파일 생성은 그 다음 승인이다.
9. 기존 `diagnosis_id` 연결로 영상 예측을 Visit에 붙인다. 예후 모델 훈련은 제외한다.

각 단계 앞에서 운영 마이그레이션, 배포, GitHub push, DeeVo 연결은 하지 않는다.

## 6. 승인 전에 보고할 항목

구현 착수 보고는 수정 파일, 마이그레이션 초안, 호환 위험, 보안 테스트, 무결성 위험, 브랜치 이름, 순서를 포함한다. 그 보고가 이 로드맵이다.

## 7. Phase 003 이후 단계

002의 파일 목록은 전체 후보다. 003은 그 목록을 삭제하지 않고, 승인된 단계만 실행한다. 브랜치 이름은 `feat/clinical-support-002`를 유지한다. 003에서 브랜치를 만들지 않았다.

| 단계 | 상태 | 범위 |
|------|------|------|
| 003 구조 정리 | 문서 완료, 구현 없음 | 재사용 분류, 경계, MEDI-DES-001 설정 자리, 004 파일 목록 |
| 004 데이터 기반 | 로컬 구현, 마이그레이션 미적용, 커밋 전 | 모델·스키마·서비스·medi006 초안·합성 테스트 10 passed |
| 005 관찰 수명주기 | 서비스 구현, 일회용 PostgreSQL에서 medi006 확인, 커밋 전 | 부모 구조, 초안·확정·정정. HTTP 없음. 가져오기는 계속 보류 |
| 006 eCRF 기초 | 서비스와 API 구현, 커밋 전 | 인증 라우트, 폼 정의·버전·응답, 기본 검증. 질의와 잠금은 보류 |
| 007 품질 MVP | 미승인 | 002 결정 규칙, finding, query |
| 008 모니터링·보고 | 미승인 | 진행 현황, 감사, 잠금, 내보내기 기록 |
| 009 임상 지능 | 미승인 | 기술통계와 베이스라인 예측. 독립 검증 전 성능 주장 없음 |
| 010 통합 검증 | 미승인 | 단위, 통합, 무결성, 접근 제어, 회귀 |

004에서 만들 파일:

- `models/clinical_support.py`
- `schemas/clinical_support.py`
- `services/clinical_records.py`
- `alembic/versions/medi006_clinical_support.py`
- `tests/test_clinical_support_models.py`

004에서 수정할 파일:

- `models/clinical.py`의 `study_kind`, `protocol_version`
- `models/__init__.py`의 export
- 이 문서 묶음의 구현 상태

004에서 제외할 파일:

- `api/patients.py`, `api/iot.py`, `api/images.py`, `api/diagnosis.py`, `config.py`
- `database.py`
- DeeVo 클라이언트와 운영 데이터 파일

## 8. 요구 구분

| 구분 | 의미 |
|------|------|
| SOURCE_SYSTEM_PROHIBITED | DeeVo 운영 데이터의 생성·수정·삭제·잠금·동기화 |
| CURRENT_PHASE_DEFERRED | 최종 제품에는 필요하나 이번 단계에서 실행하지 않음 |
| EYECARE_REQUIRED | EYECARE 자체 환경에서 제공해야 하는 최종 기능 |
| EYECARE_IMPLEMENTED | 004에서 코드로 넣은 기반 |
| EYECARE_VERIFIED | 합성 SQLite 테스트로 확인한 항목 |

DeeVo로 되돌리는 동기화는 SOURCE_SYSTEM_PROHIBITED 이다. eCRF 편집, ClinicalQuery 처리, 잠금·해제 업무, 가져오기·내보내기 실행, `alembic upgrade`는 CURRENT_PHASE_DEFERRED 이며 설계에서 빼지 않는다. 연구 설정, 대상자, Visit, 이력 있는 정정, 감사, 품질 저장, 통계, 예측, 종료는 EYECARE_REQUIRED 다.

004에서 EYECARE_IMPLEMENTED 인 것은 지원 모델, 스키마, `clinical_records` 서비스, `medi006` 초안이다. EYECARE_VERIFIED 는 아래 10개 테스트이며, 2026-10-22에 격리 SQLite에서 10 passed 다. 마이그레이션은 데이터베이스에 적용하지 않았다.

1. `study_kind` 기본값 `dataset`
2. 기존 `StudyOut` 호환
3. 연구 범위의 대상자 코드 고유
4. `StudySubject`에 직접 식별자와 치료군 열이 없음
5. Visit 관계
6. 설문 버전 관계
7. 관찰 출처
8. 정정은 후속 행
9. 기존 final 관찰 값 유지
10. finding 이 원본 값을 덮지 않음

관찰 고유 키는 `(visit_id, code, laterality, method, repeat_index, revision)` 이다. 002의 키에 `revision`을 더한 이유는, 이전 행을 UPDATE 하지 않으면서 같은 측정 키의 정정 행을 넣기 위해서다. `questionnaire_response_items`는 002의 응답 항목 테이블이며 새 개념이 아니다. `record_status` 기본값은 `final` 이다.

`medi006` 초안은 작성되었다. `alembic upgrade`는 실행하지 않았다. query, 가져오기, 치료군 테이블은 없다. 기존 환자·진단 열은 바꾸지 않았다. 합성 테스트 10개는 통과했다.

## 9. Phase 005 상태

005 지시서는 가져오기보다 부모 구조와 관찰 수명주기를 먼저 요구했다. 가져오기, eCRF 화면, 질의 업무, 잠금 업무, 예측 학습은 계속 보류다.

일회용 PostgreSQL에서 `medi006_clinical_support`까지 업그레이드가 끝났다. 그 데이터베이스는 삭제했다. 운영 적용은 아니다. 합성 SQLite 수명주기 테스트를 포함해 15 passed다. 임상 HTTP는 정책 액션이 없어 열지 않았다.

## 10. Phase 006 상태

인증된 `/api/v1/clinical-support`와 eCRF 기초, 규칙 실행이 로컬에 있다. 일회용 PostgreSQL 15에서 `medi007_ecrf_foundation`까지 적용한 뒤 데이터베이스를 삭제했다. 질의, 잠금, 가져오기, 예측 학습은 보류다. 커밋은 하지 않았다.

## 11. Phase 007 상태

질의 수명주기와 반복 가능한 품질 실행을 `feat/clinical-query-quality-007`에 두었다. 잠금, 공식 가져오기, 예측 학습, 상주 워커는 아직 없다. MEDI-DES-001의 수치 임계값과 Visit 창은 승인 원문이 없어 BLOCKED_PENDING_SOURCE 다.

008 후보는 데이터 잠금, 승인된 프로토콜 규칙 등록, 부모 저장소 통합 검토, 별도 승인이 있는 스폰서 내보내기 가져오기다. 예측 모델 학습은 그 뒤다.

## 12. Phase 008 상태

`feat/clinical-data-lock-008`의 `a8e32651c592cb30de27706c1d4c5c95c44c82c9`에 잠금, 통제된 해제, 추가 전용 감사, 연구별 준비도, 결정적 모니터링 지표가 있다. 상세 전이는 `CLINICAL-DATA-LOCK-SPEC.md`에 있다. Alembic 개정 `medi009_clinical_data_lock`은 `medi008_clinical_query` 다음 데이터베이스 순서이며 Phase 008 스키마다. 개발 단계 Phase 009가 아니고, Phase 008 완료는 이후 단계 승인을 기다리지 않는다. MEDI-DES-001 수치와 Visit 창은 승인 원문이 없어 공통 규칙으로 넣지 않았다. 가져오기, 탐색 화면, AI 재확인은 이후 요구로만 적혀 있다. 배포와 main 병합은 하지 않았다.

## 13. 이후 필수 기능

아래 세 기능은 필수 제품 능력이다. Phase 008은 정규 임상 모델, 잠금, 질의, 품질 실행과 맞물리도록 경계만 유지한다. 구현은 각각 별도 범위 승인이 나기 전에는 시작하지 않는다. 아래 후보 순서는 승인된 단계 번호가 아니다.

### EYECARE-CLINICAL-UX-001

대상자와 Visit 중심의 임상 데이터 탐색.

범위는 대상자 종단 조회, Visit 날짜 검색과 필터, 연구·사이트·대상자·Visit 이동, TBUT·OSDI·Schirmer 추세, 결측 Visit와 질의 상태, 연구 진행과 완전성 표시다. 조회는 정규 임상 모델 위의 인가된 읽기이며 임상 기록을 복제하지 않는다.

의존성은 인증된 임상 조회, 사이트 구성원, Phase 007 질의 상태, Phase 008 준비도와 잠금 상태다. 표시용 집계는 원본 관찰의 개정과 해시를 바꾸지 않는다.

수용 기준은 권한 없는 사이트가 거부되고, 같은 대상자의 확정 관찰과 설문만 종단으로 보이며, 잠긴 기록은 수정 없이 표시되고, 결측과 미해결 질의가 준비도 결과와 모순되지 않는 것이다.

후보 순서는 잠금 브랜치가 검토된 뒤의 읽기 전용 탐색이다. 단계 번호는 확정하지 않는다.

### EYECARE-CLINICAL-AI-QC-001

AI 보조 임상 수치 검증.

범위는 이상 수치, 소수점과 단위 입력 의심, 반복 측정 비교, 종단 비교, 중증도와 측정 조건의 고려, 사람 검토 권고, 검증과 정정 결정의 기록이다. 원본 관찰을 덮어쓰지 않는다. 정정 전에는 사람 검토가 필수다. 생물학적 변동을 입력 오류로 단정하지 않는다.

의존성은 관찰 개정, 추가 전용 감사, Phase 007 품질 소견, Phase 008의 결정적 모니터링 지표다. 지표에서 위험 평가, 사람 검토, 기존 정정 서비스로 이어진다. 모델 학습과 효능 주장은 이 범위에 없다.

수용 기준은 권고가 원본과 분리된 행에 남고, 사람이 거절할 수 있으며, 승인된 정정만 기존 정정 경로와 감사를 통과하고, 프로토콜 기준이 없으면 임상 오류로 단정하지 않는 것이다.

후보 순서는 결정적 지표 이후의 권고 계층이다. 학습과 운영 배치는 그 승인에 포함되지 않는다.

### EYECARE-CLINICAL-IMPORT-001

외부 임상 데이터 가져오기와 MEDI-DES-001 사례 검증. 상세는 `EXTERNAL-CLINICAL-DATA-IMPORT-SPEC.md`에 있다.

범위는 인가된 외부 EDC의 Excel/CSV, 원본 파일과 SHA-256·출처 보존, 정규 엔티티 매핑, 최종 반영 전 스테이징과 검증, 중복 검출과 멱등 재가져오기, 내보내기 스냅샷 비교, 개정과 감사, 가져온 기록의 품질 검사다. 첫 실제 사례 후보는 스폰서가 인가한 DeeVo Excel의 MEDI-DES-001이다. DeeVo는 읽기 전용으로 남는다. 개발 테스트에 실제 환자 정보를 쓰지 않는다.

의존성은 정규 임상 수명주기, Phase 007 품질 실행, Phase 008 잠금이다. 탐색은 UX-001, 이상 탐지는 AI-QC-001이며 가져오기 구현이 둘을 대신하지 않는다.

수용 기준은 같은 원본 해시의 재처리가 대상자와 관찰을 복제하지 않고, 매핑되지 않은 필드는 최종 반영되지 않으며, 가져온 관찰이 기존 개정 규칙을 따르고, 잠금이 가져오기 함수 안에서 자동으로 걸리지 않는 것이다.

후보 순서는 합성 파일 계약, 그다음 스폰서 승인 후의 MEDI-DES-001 사례다. Phase 008에서 운영 파일을 가져오지 않는다.

이 세 기능은 이후 Phase 009 요구로만 기록한다. Phase 008 구현과 검증은 이들을 포함하지 않으며, 이들의 착수 승인을 기다리지 않는다. `medi009_clinical_data_lock`이라는 Alembic 식별자는 그 이후 단계와 무관하다.
