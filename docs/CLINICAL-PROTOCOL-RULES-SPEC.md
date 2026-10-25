# 계획서 규칙 명세

규칙은 연구 범위 안에만 둔다. 전역 잠금, 준비도, 확정 판정에 넣지 않는다. 자동 추출만으로 ACTIVE가 되지 않는다.

## 진행 기록

### 2026-10-26T00:09:57+09:00 — 권고 규칙 게시

- TASK_ID: PC2-EYECARE-PROTOCOL009-PUBLICATION-003
- EXECUTION_HOST: SVG-SKLEE (PC2)
- BRANCH: feat/clinical-protocol-validation-009
- BASE_HEAD: 8fba4bfe59ccd28841653cfc55510852e1256ba3
- CODE_COMMIT: 85ef271b96e36a1a60508d66ff71ae37264235ca
- DOCS_COMMIT: 이 문서 커밋
- START_TIME_KST: 2026-10-26T00:09:57+09:00
- END_TIME_KST: 2026-10-26T00:10:50+09:00
- ELAPSED: PT53S
- DEFAULTS: `protocol_advisory_id` 없음. HTTP 본문에 선택자 없음. `enable_r1` false. 허용기간 판정 없음. 승인 전 ACTIVE 거부
- TEST_RESULTS: 이번 합성 SQLite 15 passed, 1 skipped, exit 0. PostgreSQL은 다시 실행하지 않음
- NEXT_APPROVAL: 규칙 활성화와 운영 반입은 하지 않음. Phase 010은 시작하지 않음

### 2026-10-25T23:35:00+09:00 — 승인 전 유지

- TASK_ID: PC2-EYECARE-PROTOCOL-009-FINALIZATION-002
- EXECUTION_HOST: SVG-SKLEE (PC2)
- BRANCH: feat/clinical-protocol-validation-009
- HEAD: 8fba4bfe59ccd28841653cfc55510852e1256ba3
- START_TIME_KST: 2026-10-25T23:35:00+09:00
- END_TIME_KST: 2026-10-25T23:41:49+09:00
- ELAPSED: PT6M49S
- DEFAULTS: `protocol_advisory_id` 없음. HTTP API는 이 인자를 받지 않음. `enable_r1` false. 승인 전 ACTIVE 거부. 허용기간 판정 없음
- TEST_RESULTS: 합성 SQLite 15 passed, 1 skipped, exit 0. 일회용 PostgreSQL 15 `127.0.0.1:55441`에서 `medi010_external_clinical_import`까지 올린 뒤 합성 1 passed, exit 0. 컨테이너 `eyecare-protocol-009-final-pg`는 삭제함. pytest 종료 후 Python 프로세스는 없음
- NEXT_APPROVAL: 확인 항목은 `CLINICAL-CLARIFICATION-REGISTER.md`. 커밋과 푸시 없음. Phase 010은 시작하지 않음

### 2026-10-25T13:03:02+09:00 — MEDI-DES-001 1.3 추출

- TASK_ID: PC2-EYECARE-PROTOCOL-VALIDATION-009
- EXECUTION_HOST: SVG-SKLEE (PC2)
- BRANCH: feat/clinical-protocol-validation-009
- BASE_HEAD: 8fba4bfe59ccd28841653cfc55510852e1256ba3
- START_TIME_KST: 2026-10-25T13:03:02+09:00
- END_TIME_KST: 2026-10-25T13:13:30+09:00
- ELAPSED: PT10M28S
- PROTOCOL: `MEDI-DES-001_Protocol_v1.3_19May2025_Final_20250721.pdf`
- PROTOCOL_SHA256: 39c51490afb38c8b44aebbaaa4a5bb9186e29d29292fb1726138462272fbff91
- PROTOCOL_VERSION: 1.3, 표지 날짜 2025-05-19, 93쪽
- APPROVAL_STATUS: UNRESOLVED. 서명란의 이름과 날짜가 비어 있다. 파일명의 Final은 승인 증거가 아니다
- CHANGE_TABLE: `MEDI-DES-001Protocol version 1.3_변경대비표_20250721.pdf`, SHA-256 9d1baddb2bb1be6e5f36ccf64e3871ebfcc73566f87a9dc2570eddc80b82ff39, 6쪽. 별도 승인 문서는 아니다
- TEST_RESULTS: 합성 SQLite 15 passed, 1 skipped, exit 0. 일회용 PostgreSQL 15 `127.0.0.1:55440`에서 `medi010_external_clinical_import` 이후 합성 1 passed, exit 0. 컨테이너 삭제
- NEXT_APPROVAL: 커밋과 푸시 없음. Phase 010은 시작하지 않음

## 상태

`EXTRACTED`에서 시작한다. `AWAITING_APPROVAL`인 규칙은 `ACTIVE`로 올리지 않는다. 호출자가 `protocol_advisory_id=medi-des-001-v1.3`를 줄 때만 권고 소견을 만든다. 기본값은 끄짐이다. 원본 관찰 값은 바꾸지 않는다. 새 마이그레이션은 만들지 않았다. 권고 소견은 기존 `import_validation_findings`에만 남는다.

## 규칙

| 규칙 ID | 변수 | 근거 | 논리 | 상태 |
|---|---|---|---|---|
| OSDI-ITEMS-001 | OSQ1-12 | 부록 1, p.91-93. 11.1 주석 17 | 12문항, 임상 점수 0-4. 6-12번의 해당 없음은 제외 | EXTRACTED |
| OSDI-FORMULA-001 | OSSCORE | 부록 1 계산식 | 대답한 점수 합 x 25 / 대답한 문항 수 | EXTRACTED |
| TBUT-MEAN-001 | TBUT | p.49, p.55 주석 13 | 세극등, 플루오레세인, 3회 후 평균, 단위 초 | EXTRACTED |
| SCHIRMER-METHOD-001 | STT | p.50-51, p.55 주석 14 | 비마취, 5분, mm, 소수 첫째 자리, 양안 | EXTRACTED |
| VISIT-WINDOW-001 | 방문 허용기간 | p.46 10.2.3과 p.53-59 | ±3일과 ±7일이 같은 문서에 있음. 판정하지 않음 | CONFLICTING |
| SCREENING-ID-001 | SUBJID | p.56-57 11.2.1 | 예시 SA-001. 기본 가져오기에서 강제하지 않음 | EXTRACTED |

R1은 계속 기본 꺼짐이다. 이 규칙 묶음은 R1을 켜지 않는다.
