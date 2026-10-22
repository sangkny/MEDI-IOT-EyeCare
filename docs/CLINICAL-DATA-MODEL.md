# 임상 데이터 모델

> 작업: EYECARE-CLINICAL-SUPPORT-002. 마이그레이션은 실행하지 않음.  
> 기준 커밋: `a5e2f71f98011ad52684bef62ded28432a5f8df0`  
> 기존 `ClinicalStudy`, `Patient`, `EyeExam`, `EyeImage`, `Diagnosis`, `DiagnosisReview`는 유지한다.

## 진행 기록

### 2026-10-22 22:13 KST — Phase 006 eCRF 기초 열

- 작업 ID: EYECARE-CLINICAL-SUPPORT-006
- 시작: 2026-10-22T22:13:52+09:00
- 종료: 2026-10-22T22:26:48+09:00
- PC: SVG-SKLEE, 브랜치 `feat/clinical-support-002`, HEAD `a5e2f71f98011ad52684bef62ded28432a5f8df0`
- 변경: `medi007_ecrf_foundation` 초안. `questionnaire_responses`에 사유·확정 열, `visit_form_assignments` 추가. 환자 열은 유지
- 테스트: 일회용 PostgreSQL 15에서 테이블 생성 확인. 합성 API가 설문 버전을 가리키고 확정한다
- 남은 문제: 운영 데이터베이스에는 적용하지 않음. 질의·잠금 테이블은 없음
- 다음 승인: medi007을 일회용이 아닌 환경에 적용하는 승인

### 2026-10-22 21:45 KST — Phase 005 관찰 수명주기 열

- 작업 ID: EYECARE-CLINICAL-SUPPORT-005
- 시작: 2026-10-22T21:45:27+09:00
- 종료: 2026-10-22T21:55:58+09:00
- PC: SVG-SKLEE, 브랜치 `feat/clinical-support-002`, HEAD `a5e2f71f98011ad52684bef62ded28432a5f8df0`
- 변경: 아직 어떤 데이터베이스에도 적용되지 않았던 `medi006` 초안에 `correction_reason`, `finalized_by`, `finalized_at` 추가. `record_status` 기본값 `final`은 유지
- 테스트: 초안은 유효 개정에서 빠지고, 확정 행 값은 정정 뒤에도 유지. 일회용 PostgreSQL에 네 열이 생성됨
- 남은 문제: `is_current` 열은 계속 두지 않음. MEDI-DES-001 필드 정의는 프로토콜 전이라 없음
- 다음 승인: 이 초안을 운영 데이터베이스에 적용하는 별도 승인

### 2026-10-22 17:16 KST — Phase 004B 무결성 검토

- 작업 ID: EYECARE-CLINICAL-SUPPORT-004B
- 시작: 2026-10-22T17:16:46+09:00
- 종료: 2026-10-22T17:19:41+09:00
- 경과: 2분 55초
- PC: SVG-SKLEE, 브랜치 `feat/clinical-support-002`, HEAD `a5e2f71f98011ad52684bef62ded28432a5f8df0`
- 검토: `record_status`, revision, 유효 개정, 동시 정정, 사유. 스키마 변경 없음
- 다음: 사유 열 또는 행 잠금은 별도 승인

### 2026-10-22 14:45 KST — Phase 004 모델 구현

- 작업 ID: EYECARE-CLINICAL-SUPPORT-004
- 시작: 2026-10-22T14:45:25+09:00
- 종료: 2026-10-22T14:53:33+09:00
- 경과: 8분 8초
- PC: SVG-SKLEE, 브랜치 `feat/clinical-support-002`, HEAD `a5e2f71f98011ad52684bef62ded28432a5f8df0` (커밋 전)
- 상태: 지원 테이블 EYECARE_IMPLEMENTED. 고유 키에 `revision`, `record_status` 기본값 `final`
- 테스트: 합성 SQLite에서 관계·불변 확인, 10 passed
- 다음: 마이그레이션 적용은 별도 승인

### 2026-10-22 13:53 KST — Phase 003 모델 경계

- 시작 2026-10-22T13:50:18+09:00, 종료 2026-10-22T13:53:13+09:00, 경과 2분 55초, PC SVG-SKLEE
- HEAD `a5e2f71f98011ad52684bef62ded28432a5f8df0`, 브랜치 `main`
- `StudySiteMember`는 002의 `study_site_members`와 같은 테이블. query·아카이브·치료군은 004 밖으로 기록
- 테스트와 마이그레이션은 실행하지 않음
- 다음: 004 승인 후 `medi006` 초안 작성

### 2026-10-22 13:39 KST — Phase 002 모델 초안

- 임상 엔티티, 키, 소유권, 불변 규칙을 정의. 마이그레이션 없음

## 1. 재사용

| 기존 모델 | 이 모듈에서의 위치 |
|-----------|-------------------|
| `ClinicalStudy` | 연구 루트. 데이터셋 행은 그대로 두고 `study_kind` 기본값 `dataset`을 추가한다. 전향 연구는 `prospective`. |
| `ClinicalStudyMembership` | 이미지와 정답 라벨의 AI 평가 연결. 대상자 등록으로 바꾸지 않는다. |
| `DiagnosisReview` | AI 진단의 의사 검토. 데이터 잠금과 분리한다. |
| `Patient` | 선택적 연결. 연구 식별자는 `StudySubject.subject_code`다. |
| `EyeExam` | 안저, OCT, 시야, 세극등, 굴절, 안압의 기존 검사. |
| `EyeImage`, `Diagnosis` | 영상 예측의 기존 저장소. Visit가 결과 ID만 참조한다. |

TBUT, OSDI, Schirmer 열은 기존 모델에 없다. 원본 수치는 `ClinicalObservation`과 설문 응답에 새로 둔다.

기본 키는 기존과 같이 문자열 UUID 36자다. 사용자 계정 테이블은 `shared-libraries`에 있으므로 `actor_user_id`는 외래 키 없는 문자열이다.

## 2. 경계와 소유권

연구와 기관의 경계는 `StudySite`다. 조회와 쓰기는 `study_id`와 사이트 구성원으로 제한한다.

연결 테이블 `study_site_members`는 요청 엔티티를 대체하지 않는다. 소유권 검사에 필요하다.

- 열: `id`, `site_id`, `user_id`, `role`, `created_at`
- 역할: `investigator`, `coordinator`, `reader`, `auditor`
- 고유 제약: `(site_id, user_id)`

`Patient`에는 기관 열이 없다. 기존 환자 API의 행 단위 소유권은 이 연결이 생기기 전에 만들 수 없다.

개인정보:

- 대상자 테이블에 이름, 주민등록번호, 병록번호를 두지 않는다.
- 이름이 필요하면 기존 `patients.id`만 참조한다.
- 설문 자유 서술과 내보내기 본문은 감사 이벤트에 넣지 않는다.
- 로그에는 대상자 코드, 연구 코드, 레코드 ID만 남긴다.

출처:

- 사람 입력, 장치, 가져오기, 파생 결과를 `source`로 구분한다.
- 파생 결과는 원본 행을 갱신하지 않고 새 행으로 남긴다.
- `supersedes_observation_id`는 정정 행이 이전 행을 가리킨다. 이전 행의 값은 바꾸지 않는다.
- DeeVo 운영 데이터베이스의 연결 문자열과 복제 작업은 이 모델에 없다.

## 3. 엔티티

공통 열 `created_at`은 모든 테이블에 둔다. 원본 임상 행에는 `updated_at`을 두지 않는다.

### ClinicalStudy

기존 테이블 `clinical_studies`에 호환 열만 추가한다.

| 열 | 제약 |
|----|------|
| 기존 열 | `id` PK, `code` 고유, `name`, `description`, `source_url`, `license`, 이미지 수, `label_schema_json`, `status` |
| `study_kind` | `dataset` 기본값. 기존 행은 데이터셋으로 남는다. |
| `protocol_version` | nullable 문자열 |

### StudySite

테이블 `study_sites`.

| 열 | 제약 |
|----|------|
| `id` | PK |
| `study_id` | FK `clinical_studies.id`, RESTRICT |
| `site_code` | 연구 안에서 고유 |
| `name` | 기관 표시 이름 |
| `status` | `active`, `closed` |

### StudySubject

테이블 `study_subjects`.

| 열 | 제약 |
|----|------|
| `id` | PK |
| `study_id` | FK, RESTRICT |
| `site_id` | FK `study_sites.id`, RESTRICT. 같은 연구에 속해야 한다. |
| `subject_code` | `(study_id, subject_code)` 고유 |
| `patient_id` | nullable FK `patients.id`, RESTRICT |
| `status` | `screening`, `enrolled`, `completed`, `withdrawn` |
| `enrolled_on` | 날짜, nullable |

### VisitWindow

테이블 `visit_windows`. 대상자 행이 아니라 프로토콜 정의다.

| 열 | 제약 |
|----|------|
| `id` | PK |
| `study_id` | FK, RESTRICT |
| `visit_code` | `(study_id, visit_code)` 고유 |
| `target_day` | 기준 Visit로부터의 일수 |
| `minus_days`, `plus_days` | 0 이상 |
| `is_baseline` | 연구당 하나의 기준 코드 |

### StudyVisit

테이블 `study_visits`.

| 열 | 제약 |
|----|------|
| `id` | PK |
| `subject_id` | FK `study_subjects.id`, RESTRICT |
| `visit_code` | 프로토콜 코드 |
| `repeat_no` | 1부터. `(subject_id, visit_code, repeat_no)` 고유 |
| `occurred_on` | 실제 날짜 |
| `eye_exam_id` | nullable FK `eye_exams.id`, RESTRICT |
| `diagnosis_id` | nullable FK `diagnoses.id`, RESTRICT. 영상 예측 참조 |
| `window_id` | nullable FK `visit_windows.id` |

### QuestionnaireDefinition

테이블 `questionnaire_definitions`.

| 열 | 제약 |
|----|------|
| `id` | PK |
| `study_id` | FK, RESTRICT |
| `code` | `(study_id, code)` 고유. 초기 코드 `OSDI` |
| `title` | 표시 이름 |

### QuestionnaireVersion

테이블 `questionnaire_versions`. 응답이 생기면 내용 해시는 바꾸지 않는다.

| 열 | 제약 |
|----|------|
| `id` | PK |
| `definition_id` | FK, RESTRICT |
| `version_number` | 정의 안에서 고유, 1부터 |
| `content_hash` | 항목 정의의 SHA-256 |
| `items_json` | 항목 코드, 형식, 허용 범위, 필수 여부 |
| `published_at` | 시각 |

### QuestionnaireResponse

테이블 `questionnaire_responses`. 항목 값은 `questionnaire_response_items`에 둔다.

응답 머리:

| 열 | 제약 |
|----|------|
| `id` | PK |
| `version_id` | FK `questionnaire_versions.id`, RESTRICT |
| `visit_id` | FK `study_visits.id`, RESTRICT |
| `status` | `draft`, `complete` |
| `recorded_by` | 사용자 ID |
| `content_hash` | 완료 시점의 항목 값 해시 |

항목 테이블:

| 열 | 제약 |
|----|------|
| `id` | PK |
| `response_id` | FK, RESTRICT |
| `item_code` | `(response_id, item_code)` 고유 |
| `value_json` | 원본 값 |
| `captured_at` | 시각 |

완료 응답과 항목 값은 갱신하지 않는다. 수정을 허용하는 경우는 잠금 전의 `draft`뿐이다. 완료 후 변경은 새 응답과 `supersedes_response_id`로 남긴다.

### ClinicalObservation

테이블 `clinical_observations`.

| 열 | 제약 |
|----|------|
| `id` | PK |
| `visit_id` | FK, RESTRICT |
| `code` | `TBUT`, `SCHIRMER`, 기존 검사에서 복사한 코드 |
| `laterality` | `OD`, `OS`, `OU`, `NA` |
| `method` | Schirmer의 `with_anesthesia`, `without_anesthesia`. 해당 없으면 `NA` |
| `repeat_index` | 1부터. TBUT 반복 측정 |
| `value_number` | nullable 수치 |
| `value_text` | nullable. 수기 단위 표기 |
| `unit` | `s`, `mm` 등 |
| `source` | `manual`, `device`, `import`, `derived` |
| `source_observation_id` | nullable. 파생 결과의 입력 |
| `supersedes_observation_id` | nullable self FK |
| `eye_exam_id` | nullable FK |
| `model_name`, `model_version` | 파생 예측에만 채운다 |
| `recorded_by`, `recorded_at` | 입력 주체와 시각 |
| `row_hash` | 값과 코드의 SHA-256 |

고유 제약: `(visit_id, code, laterality, method, repeat_index)`.

영상 모델의 본 결과는 기존 `diagnoses`에 둔다. 이 테이블의 `derived` 행은 방문에 연결한 참조와 수치 예후처럼 기존 진단 테이블에 없는 값만 담는다. 예후 MLP 훈련은 이 스키마의 범위가 아니다.

### DataQualityRule

테이블 `data_quality_rules`. 환자 행과 분리한다.

| 열 | 제약 |
|----|------|
| `id` | PK |
| `study_id` | FK, RESTRICT |
| `code` | 규칙 코드 |
| `version_number` | `(study_id, code, version_number)` 고유 |
| `severity` | `warning`, `error` |
| `logic_json` | 임계값과 대상 코드 |
| `content_hash` | 로직 해시 |
| `status` | `active`, `retired` |

활성 규칙을 고칠 때는 버전을 올리고 이전 버전을 `retired`로 둔다. 이전 버전의 본문은 바꾸지 않는다.

### DataQualityFinding

테이블 `data_quality_findings`.

| 열 | 제약 |
|----|------|
| `id` | PK |
| `rule_id` | FK, RESTRICT |
| `rule_version` | 판정 당시 버전 |
| `study_id`, `subject_id`, `visit_id` | 범위. subject와 visit는 nullable일 수 있다. |
| `target_type` | `observation`, `response`, `visit`, `subject` |
| `target_id` | 대상 PK |
| `fingerprint` | 규칙, 대상, 입력 해시 |
| `status` | `open`, `acknowledged`, `resolved`, `waived`, `superseded` |
| `message_code` | 고정 코드. 자유 서술에 원본 값을 넣지 않는다. |
| `waive_reason` | `waived`일 때만 |
| `closed_by`, `closed_at` | nullable |

같은 `fingerprint`의 `open` 행은 하나다. 상태 전이는 이 테이블에서만 허용하고 감사 이벤트를 남긴다. 대상 임상 행은 갱신하지 않는다.

### ClinicalAuditEvent

테이블 `clinical_audit_events`. 추가만 허용한다.

| 열 | 제약 |
|----|------|
| `id` | PK |
| `study_id` | FK, RESTRICT |
| `site_id` | nullable FK |
| `actor_user_id` | 문자열 |
| `action` | `create`, `complete`, `amend`, `lock`, `unlock`, `export_request`, `quality_open`, `quality_transition` |
| `target_type`, `target_id` | 대상 |
| `occurred_at` | 시각 |
| `request_id` | 요청 상관 ID |
| `payload_hash` | 본문 해시. 본문 원문은 저장하지 않는다. |

기존 파트너 감사 조회는 이 테이블을 읽지 않는다.

### DataLockRecord

테이블 `data_lock_records`.

| 열 | 제약 |
|----|------|
| `id` | PK |
| `study_id` | FK |
| `target_type` | `study`, `site`, `subject`, `visit` |
| `target_id` | 대상 |
| `action` | `lock`, `unlock` |
| `reason` | 필수 |
| `actor_user_id` | 문자열 |
| `occurred_at` | 시각 |

잠금과 해제는 새 행으로 남긴다. 현재 상태는 대상별 마지막 행이다. 잠긴 Visit에는 관찰과 완료 응답을 추가하지 않는다.

### DataExportRecord

테이블 `data_export_records`.

| 열 | 제약 |
|----|------|
| `id` | PK |
| `study_id` | FK |
| `site_id` | nullable. 비어 있으면 연구 전체이며 `auditor`만 요청할 수 있다. |
| `actor_user_id` | 요청자 |
| `filter_hash` | 조건 해시 |
| `status` | `requested`, `completed`, `failed`, `expired` |
| `row_count` | nullable |
| `output_sha256` | 생성 파일 해시, nullable |
| `requested_at`, `completed_at` | 시각 |

내보내기 파일은 이 테이블과 Git에 두지 않는다. DeeVo 내보내기 API는 호출하지 않는다.

## 4. 기존 API와의 연결

- `GET/POST /clinical/studies`와 멤버십, 승격, 검토, FHIR는 경로와 응답을 유지한다.
- 새 라우트는 `/api/v1/clinical/support/...` 로 둔다. 데이터셋 연구에 support 쓰기를 하지 않는다.
- `POST /patients`와 `POST /diagnosis/exam`의 스키마는 보안 조치에서 유지한다.
- `StudyVisit.eye_exam_id`와 `diagnosis_id`는 기존 검사가 있을 때만 채운다.
- IoT 메모리 측정은 자동으로 관찰 행이 되지 않는다. 명시적 전사 API가 승인되기 전에는 연결하지 않는다.
- `database.create_tables()`는 임상 연구 모델을 가져오지 않는다. 새 테이블은 Alembic으로만 만들고, 그 마이그레이션은 이 문서의 승인 뒤에 작성한다.

## 5. 감사와 버전

- 설문 버전과 품질 규칙 버전은 응답 또는 판정이 참조한 뒤 본문을 바꾸지 않는다.
- 관찰, 완료 응답, 감사, 잠금, 내보내기 요청은 삭제하지 않는다.
- 품질 판정과 예측 파생은 원본 `value_number`를 갱신하지 않는다.
- 모든 support 쓰기는 `ClinicalAuditEvent` 한 행을 같은 트랜잭션에 넣는다.

## 6. Phase 003에서 유지한 결정

002의 키, 사이트 경계, 대상자 비식별, 원본 불변, `study_kind` 기본값 `dataset`은 유지한다. 환자·진단 열은 MVP에서 바꾸지 않는다.

`study_site_members`는 002의 연결 테이블이자 003의 `StudySiteMember`다. 별도 테이블을 추가하지 않는다. 역할은 `investigator`, `coordinator`, `reader`, `auditor`다.

`main.py`가 `create_tables()` 직접 호출을 금지하므로, 004에서 `database.py`의 `create_all` import를 늘리지 않는다. 스키마는 Alembic만 사용한다. 이 좁힘은 002의 `database.py` 수정 제안을 대체한다.

## 7. 이후 단계의 추가 엔티티

004 마이그레이션에는 넣지 않는다.

| 엔티티 | 단계 | 관계 |
|--------|------|------|
| `ClinicalQuery` | 007 | `finding_id` FK. 상태 `open`, `answered`, `closed`. finding 상태를 대체하지 않는다. |
| `SourceArchive` | 005 | 원본 파일 바이트는 Git 밖에 둔다. `sha256`, `study_id`, `source_system`, `archived_at`, `byte_size` |
| `ImportManifest` | 005 | 아카이브 ID, 필드 맵 버전, 스테이징 결과, 데이터셋 버전 |
| 치료군 배정 | 눈가림 정책 승인 후 | `StudySubject` 열이 아니다. 운영 역할의 API에 포함하지 않는다. |

정정은 기존 `supersedes_observation_id`와 새 응답 행을 유지한다. query 답변도 원본 값을 갱신하지 않는다.

## 8. MEDI-DES-001 설정

연구 코드 `MEDI-DES-001`, `study_kind=prospective`. 방문·설문·관찰 코드의 후보는 Screening, Enrollment, Baseline, TBUT, OSDI, Schirmer, adherence, safety, follow-up, protocol deviation이다. 이 목록은 프로토콜과 대조하기 전의 범위다. 일수와 필수 항목은 `VisitWindow`와 `DataQualityRule` 버전으로 넣으며, 공통 서비스에 상수로 두지 않는다. 승인된 프로토콜 파일이 로컬에 없으므로 이 절은 필드 정의를 확정하지 않는다.

## 9. Phase 004 구현 차이

EYECARE_IMPLEMENTED. 환자·진단 열은 바꾸지 않았다.

- `clinical_observations` 고유 키에 `revision`을 추가했다. 이전 final 행을 UPDATE 하지 않고 같은 측정 키의 정정 행을 저장하기 위한 변경이다.
- `record_status` 기본값은 `final`이다.
- `questionnaire_response_items`는 002에 있던 응답 항목 테이블이다.
- `ClinicalQuery`, `SourceArchive`, `ImportManifest`, 치료군 테이블은 만들지 않았다. CURRENT_PHASE_DEFERRED 이며 EYECARE_REQUIRED 로 남는다.
- DeeVo 동기화 열은 없다. SOURCE_SYSTEM_PROHIBITED.

## 10. Phase 004B에서 보류한 스키마 결정

스키마는 바꾸지 않았다.

- 현재 유효 행은 측정 키별 최대 `revision`이다. 별도 `is_current` 열은 이전 행 UPDATE가 필요하므로 넣지 않는다.
- 정정 사유를 읽을 수 있는 열은 없다. 감사 설계는 본문 대신 해시를 유지한다. 사유 평문을 남기려면 새 열이 필요하고, 그건 승인 사항이다.
- `draft` 값은 열이 허용하지만 004 서비스는 쓰지 않는다. eCRF draft 저장은 CURRENT_PHASE_DEFERRED 다.

## 11. Phase 005 수명주기 열

004B가 보류했던 사유 열을, 아직 적용된 적 없는 `medi006` 초안에 넣었다. 이미 적용된 데이터베이스를 고친 변경이 아니다.

- `correction_reason`는 정정 후속 행에만 채운다. 빈 사유는 서비스가 거절한다.
- `finalized_by`, `finalized_at`는 명시적 확정과 정정 후속 행에 남는다.
- `record_status` 기본값은 계속 `final`이다. `record_observation`의 즉시 확정 경로를 유지하기 위해서다.
- 현재 유효 행은 `record_status=final`인 최대 `revision`이다. `is_current` 열은 없다.
- 감사 행은 002와 같이 본문 대신 해시를 저장한다. 정정 사유 평문은 후속 관찰 행의 `correction_reason`에 있다. 감사 해시 입력에는 사유가 포함된다.
- 환자·검사·진단 열과 치료군 열은 추가하지 않았다.

## 12. Phase 006 eCRF 기초

`medi007_ecrf_foundation`은 `medi006` 다음의 추가 개정이다. 운영 데이터베이스에는 적용하지 않았다.

- `questionnaire_responses.correction_reason`, `finalized_by`, `finalized_at`
- `visit_form_assignments`: 연구, Visit 코드, 설문 정의. 문항 본문은 버전 `items_json`에 있다.
- 문항 객체는 `code`, `type`, `required`, 숫자 범위 `min`/`max`를 담을 수 있다. MEDI-DES-001의 확정 문항은 아니다.
- 치료군과 배정 열은 계속 없다.
