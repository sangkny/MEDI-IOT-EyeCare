# Data Quality Engine 명세

> 작업: EYECARE-CLINICAL-SUPPORT-002. 구현과 마이그레이션은 시작하지 않음.  
> 원본 임상 값은 판정 흐름에서 바꾸지 않는다. 판정은 `data_quality_findings`에만 쓴다.  
> 임계값은 설계 기본값이다. 임상 확정 전이며 제품의 진단 기준으로 쓰지 않는다.

## 진행 기록

### 2026-10-24T16:45:06+09:00 — Phase 008 게시

- TASK_ID: PC2-EYECARE-PHASE008-PUBLISH-001
- EXECUTION_HOST: SVG-SKLEE
- BRANCH: feat/clinical-data-lock-008
- HEAD_BEFORE: 87aea032d7af8ec1723036a9ca7c1183dcdbd7a3
- HEAD_AFTER: 이 게시 커밋
- START_TIME_KST: 2026-10-24T16:44:02+09:00
- END_TIME_KST: 2026-10-24T16:45:06+09:00
- TEST_RESULTS: SQLite 42 passed, 3 skipped. 준비도·지표는 합성 데이터
- PUSH: origin `feat/clinical-data-lock-008`만

### 2026-10-23T20:28:50+09:00 — Phase 008 준비도

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
- FILES_CHANGED: `services/clinical_readiness.py`, `services/clinical_monitoring.py`
- TEST_RESULTS: 승인 프로토콜이 없으면 `BLOCKED_PENDING_PROTOCOL`. 열린 소견은 잠금을 막고 관찰 해시는 유지. SQLite 20 passed
- MIGRATION: 없음. 품질 테이블은 007을 유지
- REMAINING_ISSUES: MEDI-DES-001 임계값은 계속 BLOCKED_PENDING_SOURCE. 예측은 DEFERRED
- NEXT_APPROVAL: 승인된 프로토콜 원문이 생긴 뒤의 규칙 등록

### 2026-10-23 09:15 KST — Phase 007 품질 검증

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
- FILES_CHANGED: `services/clinical_quality.py`, `services/clinical_monitoring.py`
- TEST_RESULTS: 결측, 중복, 개정, 재실행, 관찰 해시 유지 PASS. 예측값은 null
- REMAINING_ISSUES: MEDI-DES-001 임계값은 BLOCKED_PENDING_SOURCE. 상주 워커 없음

### 2026-10-23 00:35 KST — Phase 007 품질 실행

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
- FILES_CHANGED: `services/clinical_quality.py`, `services/clinical_monitoring.py`
- TEST_RESULTS: 결측, 범위, 중복, 개정 불일치, Visit 날짜 역전, 교차 항목, 재실행, 관찰 해시 유지 PASS
- REMAINING_ISSUES: MEDI-DES-001 임계값과 Visit 창은 BLOCKED_PENDING_SOURCE. 예측 모델은 DEFERRED. 상주 워커는 없음

### 2026-10-22 22:42 KST — PC2 기능 브랜치 게시

- 작업 ID: PC2-CLINICAL-GIT-PUBLISH-001
- 시작: 2026-10-22T22:42:55+09:00
- 종료: 2026-10-22T22:45:21+09:00
- PC: SVG-SKLEE / PC2
- 저장소: MEDI-IOT-EyeCare `feat/clinical-support-002`, 커밋 `3d8e5702e439db7cfd658e42b6977520845260a2`
- push: origin 기능 브랜치
- 테스트: 품질 규칙이 관찰 값을 유지하는 합성 테스트가 19 passed에 포함
- 남은 문제: 예측 학습은 없음
- 다음 승인: 브랜치 검토

### 2026-10-22 22:13 KST — Phase 006 규칙 실행 기초

- 작업 ID: EYECARE-CLINICAL-SUPPORT-006
- 시작: 2026-10-22T22:13:52+09:00
- 종료: 2026-10-22T22:26:48+09:00
- PC: SVG-SKLEE, 브랜치 `feat/clinical-support-002`, HEAD `a5e2f71f98011ad52684bef62ded28432a5f8df0`
- 변경: `services/clinical_quality.py`. `logic_json.kind`로 범위, 필수 유효 개정, 중복 상한, 설문 완전성, 개정 사슬, 출처를 검사한다. finding만 쓰고 관찰 값은 유지한다
- 테스트: 범위 밖 값의 finding 생성 뒤 관찰 해시가 같고, 검토 후 재실행은 새 finding을 만들지 않음. PASS
- 남은 문제: MEDI-DES-001 임계값은 넣지 않음. 예측 모델은 없음
- 다음 승인: 프로토콜이 정한 `logic_json`을 연구에 등록하는 승인

### 2026-10-22 21:45 KST — Phase 005 품질 입력의 경계

- 작업 ID: EYECARE-CLINICAL-SUPPORT-005
- 시작: 2026-10-22T21:45:27+09:00
- 종료: 2026-10-22T21:55:58+09:00
- PC: SVG-SKLEE, 브랜치 `feat/clinical-support-002`, HEAD `a5e2f71f98011ad52684bef62ded28432a5f8df0`
- 변경: 규칙 실행과 예측 학습은 추가하지 않음. 유효 개정 조회가 `record_status=final`의 최대 `revision`만 반환
- 테스트: 초안만 있는 측정 키의 유효 개정은 없음. finding이 관찰 값을 유지하는 004 테스트는 계속 통과
- 남은 문제: 결측·범위·Visit 창 규칙은 007
- 다음 승인: 프로토콜이 확정된 뒤 `logic_json`에 연구별 임계값을 넣는 승인

### 2026-10-22 17:16 KST — Phase 004B 품질 저장 재확인

- 작업 ID: EYECARE-CLINICAL-SUPPORT-004B
- 시작: 2026-10-22T17:16:46+09:00
- 종료: 2026-10-22T17:19:41+09:00
- 경과: 2분 55초
- PC: SVG-SKLEE, 브랜치 `feat/clinical-support-002`, HEAD `a5e2f71f98011ad52684bef62ded28432a5f8df0`
- 결과: finding 삽입이 관찰 값을 바꾸지 않는 테스트는 다시 통과. 규칙 실행은 그대로 보류
- 다음: 007

### 2026-10-22 14:45 KST — Phase 004 품질 저장

- 작업 ID: EYECARE-CLINICAL-SUPPORT-004
- 시작: 2026-10-22T14:45:25+09:00
- 종료: 2026-10-22T14:53:33+09:00
- 경과: 8분 8초
- PC: SVG-SKLEE, 브랜치 `feat/clinical-support-002`, HEAD `a5e2f71f98011ad52684bef62ded28432a5f8df0` (커밋 전)
- 상태: finding 저장은 EYECARE_IMPLEMENTED. 규칙 실행은 CURRENT_PHASE_DEFERRED
- 테스트: finding 삽입 후 관찰 해시 유지, 합성 SQLite 통과
- 다음: 007에서 결정 규칙 실행

### 2026-10-22 13:53 KST — Phase 003 품질 MVP 범위

- 시작 2026-10-22T13:50:18+09:00, 종료 2026-10-22T13:53:13+09:00, 경과 2분 55초, PC SVG-SKLEE
- HEAD `a5e2f71f98011ad52684bef62ded28432a5f8df0`
- 002 결정 규칙을 유지하고 query·교차 항목·009 지능의 경계를 10장에 추가
- 엔진 테스트는 실행하지 않음. MEDI-DES-001 임계값은 프로토콜 대조 전
- 다음: 007은 별도 승인

### 2026-10-22 13:39 KST — Phase 002 품질 명세

- 결측, 범위, 중복, Visit 창, TBUT, OSDI, Schirmer, finding 수명을 정의

## 1. 입력과 출력

입력은 한 Visit의 완료된 설문 응답, `clinical_observations`, `visit_windows`, 활성 `data_quality_rules`다. IoT 메모리와 DeeVo는 입력이 아니다.

출력은 finding 행과 `quality_open` 또는 `quality_transition` 감사 이벤트다. 관찰의 `value_number`, `row_hash`, 설문 항목 값은 트랜잭션에서 읽기만 한다.

엔진 데이터베이스 권한의 목표는 임상 원본 SELECT, finding INSERT, finding 상태 UPDATE, 감사 INSERT다. 권한 스크립트는 이 단계에서 실행하지 않는다.

## 2. 공통 판정

| 코드 | 조건 | 기본 심각도 |
|------|------|-------------|
| `MISSING_VALUE` | Visit 코드의 필수 관찰 또는 필수 설문 항목이 없다. | error |
| `DUPLICATE_OBSERVATION` | 같은 Visit, 코드, 측, 방법, `repeat_index`가 고유 제약을 넘기려 한다. 저장 전에 거절하고 finding을 남긴다. | error |
| `INVALID_RANGE` | 규칙의 최소·최대 밖이다. | error |
| `VISIT_WINDOW` | 기준 Visit의 `occurred_on`에 `target_day`를 더한 구간 밖에 실제 날짜가 있다. 기준 Visit가 없으면 error. | error |
| `PROTOCOL_INCOMPLETE` | 필수 설문 완료와 필수 관찰이 있고, 그 대상의 error finding이 `open`이 아닐 때 통과. 하나라도 실패하면 이 요약 finding을 연다. | error |

중복 판정은 반복 측정을 막지 않는다. TBUT의 서로 다른 `repeat_index`는 중복이 아니다.

재실행은 같은 fingerprint의 `open` 행을 다시 만들지 않는다. 입력이 정정 행으로 바뀌어 조건이 사라지면 기존 finding을 `resolved`로 전이한다. 규칙 버전이 올라가면 이전 finding을 `superseded`로 전이하고 새 fingerprint로 연다.

## 3. TBUT

코드 `TBUT`. 단위 `s`. 측은 `OD` 또는 `OS`. 방법 `NA`.

- 반복 기본 개수는 3이다. 개수가 3보다 작으면 `TBUT_REPEAT_COUNT` warning.
- 각 값은 0 이상 60 이하다. 밖이면 `INVALID_RANGE` error.
- 반복값의 최대와 최소 차이가 5초를 넘으면 `TBUT_VARIABILITY` warning.
- 변동성 판정은 반복 행을 수정하지 않는다. 대표값을 원본 위에 덮어쓰지 않는다.

## 4. OSDI

정의 코드 `OSDI`. 항목은 12개, 각 값은 정수 0 이상 4 이하다.

완료 점수:

```
(응답 합 × 25) / 응답한 항목 수
```

이 식은 출판된 OSDI 채점 형태를 구현 규칙으로 채택한 것이다. 임상 컷오프는 규칙에 넣지 않는다.

- 항목이 12개 미만이면 `OSDI_INCOMPLETE` error. 점수를 확정 값으로 저장하지 않는다.
- 범위 밖 항목은 `INVALID_RANGE` error.
- 저장된 점수 열이 생기면 엔진이 항목으로 다시 계산한 값과 비교한다. 다르면 `OSDI_SCORE_MISMATCH` error. 저장된 점수를 고치지 않는다.
- 완료 응답의 항목은 품질 판정 중 바꾸지 않는다.

## 5. Schirmer

코드 `SCHIRMER`. 단위 `mm`. 측은 `OD` 또는 `OS`.

- `method`는 `with_anesthesia` 또는 `without_anesthesia`다. `NA`이면 `SCHIRMER_METHOD_MISSING` error.
- 값은 0 이상 35 이하다. 밖이면 `INVALID_RANGE` error.
- 마취 여부에 따라 행을 합치거나 평균으로 원본을 대체하지 않는다.

## 6. 프로토콜 준수

Visit 코드마다 활성 규칙이 필수 관찰 코드와 필수 설문 코드를 가진다. 초기 전향 프로토콜의 기본 집합은 양안 `TBUT` 3회, 양안 `SCHIRMER` 1회와 방법, `OSDI` 완료 응답이다. 데이터셋 연구(`study_kind=dataset`)에는 이 집합을 적용하지 않는다.

`PROTOCOL_INCOMPLETE`는 개별 finding이 열린 이유를 복제하지 않는다. 대상 Visit와 실패 규칙 코드만 가리킨다.

## 7. Finding 수명

```
open → acknowledged → resolved
open → waived
open → superseded
```

- `acknowledged`는 검토자가 조건을 확인한 상태다. 원본은 그대로다.
- `resolved`는 이후의 정정 행 때문에 조건이 사라진 상태다.
- `waived`는 `auditor` 또는 `investigator`의 사유가 필요하다.
- `superseded`는 규칙 버전 교체다.
- 전이는 `clinical_audit_events`에 남긴다. finding을 삭제하지 않는다.

잠긴 Visit에서는 새 판정을 열 수 있고, 원본 추가는 거절한다. 잠금은 품질 상태를 자동으로 `waived`로 바꾸지 않는다.

## 8. 예측 분석과의 경계

기존 안저 진단과 `diagnoses` 행은 품질 엔진의 수정 대상이 아니다. Visit의 `diagnosis_id`가 가리키는 진단이 없어도 `PROTOCOL_INCOMPLETE`에 넣지 않는다. 영상 예측의 성능 기준은 `SAMD-CHECKLIST.md`와 예후 설계 문서에 둔다.

파생 관찰은 원본과 같은 불변 규칙을 따른다. 품질 엔진은 파생 값을 원본 코드의 결측을 메우는 값으로 사용하지 않는다.

## 9. 검증 픽스처

합성 대상자만 사용한다. 운영 환자와 DeeVo 응답은 사용하지 않는다.

- 필수 TBUT가 없으면 `MISSING_VALUE`이고 관찰 행 수는 그대로다.
- 같은 `repeat_index`의 둘째 TBUT는 저장되지 않는다.
- 61초 TBUT는 error다.
- 0초, 3초, 9초는 변동성 warning이고 세 행의 해시는 유지된다.
- OSDI 11항은 점수를 확정하지 않는다.
- OSDI 12항의 재계산 점수가 저장 값과 같으면 점수 finding이 없다.
- Schirmer 방법 없음과 36mm는 error다.
- 기준일 + `target_day`에서 창 밖 날짜는 `VISIT_WINDOW`다.
- 판정 전후 `clinical_observations.row_hash` 집합은 같다.

## 10. Phase 003 MVP 범위

002의 결측, 범위, 중복, Visit 창, 프로토콜, TBUT 반복·변동, OSDI 완전성·재계산, Schirmer 방법·범위를 MVP의 결정적 규칙으로 유지한다. 임계값은 플랫폼 서비스 상수가 아니라 연구별 `logic_json`이다. MEDI-DES-001에 넣을 초기 값은 002의 설계 기본값이며, 승인 프로토콜과 대조하기 전에는 미확정이다.

007에서 finding과 분리해 추가하는 것:

- 교차 항목: Schirmer 방법 누락, 프로토콜이 요구한 양안 코드 누락
- `ClinicalQuery`: finding을 가리키는 질의 상태. finding의 `open`/`waived` 전이를 지우지 않는다.
- 순응도와 종료점 완전성: 프로토콜 필드가 확정된 뒤의 연구 규칙

종단 급변, 결측 예측, 질의 우선순위, 방문 지연·탈락 위험은 009의 임상 지능이다. MVP 규칙이 관찰 값을 고치거나 치료군을 추론하지 않는다. 데이터셋 연구에는 이 규칙 묶음을 적용하지 않는다.

## 11. Phase 004에서 구현된 범위

규칙 판정 함수는 아직 없다. CURRENT_PHASE_DEFERRED.

EYECARE_IMPLEMENTED 는 `DataQualityRule`, `DataQualityFinding` 저장과 `record_quality_finding`이다. 이 함수는 관찰의 `value_number`와 `row_hash`를 쓰지 않는다. EYECARE_VERIFIED 는 합성 행 하나의 finding 삽입 테스트다. TBUT, OSDI, Schirmer 규칙 실행은 007까지 EYECARE_REQUIRED 로 남는다.

## 12. Phase 005에서 준비한 입력

규칙 함수는 추가하지 않았다. 이후 완전성, 범위, 중복, Visit 시점, 설문 불일치, 개정 이상 규칙은 `get_effective_observation`이 돌려주는 확정 행만 읽는다. 초안은 확정 관찰로 세지 않는다. 예측 결과는 관찰 값을 덮어쓰지 않는다. 이 단계에서 모델을 학습하지 않았다. 통계 집계와 위험 점수는 009까지 보류한다.

## 13. Phase 006 규칙 실행

`run_quality_rules`가 활성 규칙의 `logic_json.kind`를 읽는다. 지원하는 kind는 `numeric_range`, `required_effective`, `max_finals`, `questionnaire_complete`, `revision_chain`, `provenance`다. 임계값은 규칙 JSON에만 있다. 같은 fingerprint의 open 또는 reviewed finding이 있으면 재실행은 새로 만들지 않는다. `review_finding`은 상태를 `reviewed`로 바꾸고 관찰 값을 유지한다. 예측 인터페이스는 이 함수가 관찰을 수정하지 않는다는 경계다.

## 14. Phase 007 실행 모델

같은 함수가 연구, 대상자, Visit, 폼 범위를 받는다. 입력 직후 검증은 `validate_after_entry`이며 Visit 범위와 `trigger=entry`를 쓴다. 상주 워커는 시작하지 않는다. 실행마다 `quality_evaluation_runs` 한 행을 남긴다.

추가 kind는 `missing_value`, `duplicate_observation`, `visit_date_order`, `questionnaire_incomplete`, `cross_field`다. `blocked_source`는 finding을 만들지 않는다. fingerprint에는 규칙 버전, 대상, 원본 revision, 평가 범위가 들어간다. 같은 범위의 open 또는 reviewed finding은 다시 만들지 않고, 기존 행은 덮어쓰지 않는다.

MEDI-DES-001 카탈로그의 존재 확인 규칙은 합성 시연이다. Visit 시점, 순응, 추적 누락, 프로토콜 이탈은 `BLOCKED_PENDING_SOURCE`이며 수치 임계값을 넣지 않았다. 치료군은 읽지 않는다.

완전성 점수와 신뢰 지표는 관찰 테이블 밖에 계산한다. 결측 위험, 방문 미준수, 측정 이상, 완료 예측은 `DEFERRED`이고 `predicted_value`는 null이다. 예측값이 측정값을 대체하지 않는다.
