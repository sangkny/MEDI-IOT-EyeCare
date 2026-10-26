# 임상 확인 등록부

환자 측정값, 식별자, 배정은 적지 않는다. 비숫자 칸은 오류로 단정하지 않는다. 규칙은 승인 전까지 권고이며 기본 가져오기에서 꺼져 있다.

## 진행 기록

### 2026-10-26T15:51:33+09:00 — 계획서 1.10 게시

- TASK_ID: PC2-EYECARE-PROTOCOL-V110-PUBLICATION-004
- EXECUTION_HOST: SVG-SKLEE (PC2)
- BRANCH: feat/clinical-protocol-validation-009
- BASE_HEAD: 388a8ea9001904b5a4a1d48ab0f778fd9b299c2d
- CODE_COMMIT: 574b9527fbed211d6ef2f75699888f8db58f50d6 `feat: update clinical protocol advisory rules for v1.10`
- DOCS_COMMIT: 이 문서 커밋 `docs: reconcile v1.10 protocol and export validation`
- START_TIME_KST: 2026-10-26T15:51:33+09:00
- END_TIME_KST: 2026-10-26T15:53:37+09:00
- ELAPSED: PT2M4S
- PROTOCOL_SHA256: 9e24fcedbd869e4e2b88d8b33e32acf617d4fd541199c78cd4c75d6444e2ac44
- PROTOCOL_VERSION: 1.10, 2026-07-01, 95쪽. 승인 상태는 UNRESOLVED
- TEST_RESULTS: 이번 합성 SQLite 15 passed, 1 skipped, exit 0. 이번 일회용 PostgreSQL 15 `127.0.0.1:55442`에서 `medi010_external_clinical_import` 이후 합성 1 passed, exit 0. 컨테이너 `eyecare-protocol-v110-pg` 삭제. pytest 종료 후 Python 프로세스는 없음
- RESOLVED_BY_V110: 방문 6 OSDI. 1.3 부록의 방문 1-5 기록은 유지. 1.4-1.9 개정 시점은 특정하지 않음
- REMAINING: 서명 승인, ±3일과 ±7일, 방문 4 MEDI-EYE 치료, OSDI 반올림, 단위 문자만 있는 칸, 연구 귀속, R1 운영 승인, 반복 양식 원본 키
- PUSH: origin `feat/clinical-protocol-validation-009`만 일반 푸시. 규칙 활성화, 운영 반입, 배포, PR 병합은 하지 않음
- NEXT_APPROVAL: Phase 010은 시작하지 않음

### 2026-10-26T15:01:00+09:00 — 계획서 1.10 대조

- TASK_ID: 로컬 계획서 1.10 반영
- EXECUTION_HOST: SVG-SKLEE (PC2)
- BRANCH: feat/clinical-protocol-validation-009
- HEAD_BEFORE: 388a8ea9001904b5a4a1d48ab0f778fd9b299c2d
- START_TIME_KST: 2026-10-26T15:01:00+09:00
- END_TIME_KST: 2026-10-26T15:04:39+09:00
- ELAPSED: PT3M39S
- PROTOCOL: `MEDI-DES-001_Protocol_V1.10_01Jul2026.pdf`, 95쪽, 3582719바이트
- PROTOCOL_SHA256: 9e24fcedbd869e4e2b88d8b33e32acf617d4fd541199c78cd4c75d6444e2ac44
- PROTOCOL_VERSION: 1.10, 표지 날짜 2026-07-01. 서명란의 이름과 날짜는 비어 있음
- PACK_ID: `medi-des-001-v1.10`. 기본 가져오기는 계속 꺼져 있음
- TEST_RESULTS: 합성 SQLite 15 passed, 1 skipped, exit 0. PostgreSQL은 다시 실행하지 않음
- RESOLVED_IN_1_10: 부록 1 방문 칸은 방문 1, 2, 3, 4, 6이다. 11.1 OSDI 일정과 같다
- REMAINING: 10.2.3의 ±3일과 11.1·11.2의 ±7일. 서명 승인. 1.4–1.9 전문은 로컬에 없음. 반올림 자릿수, 연구 귀속, R1, 반복 양식 키
- NEXT_APPROVAL: 커밋과 푸시 없음. 규칙 활성화와 Phase 010은 시작하지 않음

### 2026-10-26T00:09:57+09:00 — 계획서 검증 게시

- TASK_ID: PC2-EYECARE-PROTOCOL009-PUBLICATION-003
- EXECUTION_HOST: SVG-SKLEE (PC2)
- BRANCH: feat/clinical-protocol-validation-009
- BASE_HEAD: 8fba4bfe59ccd28841653cfc55510852e1256ba3
- CODE_COMMIT: 85ef271b96e36a1a60508d66ff71ae37264235ca `feat: add advisory protocol validation for clinical imports`
- DOCS_COMMIT: 이 문서 커밋 `docs: record Sponsor Protocol v1.3 validation evidence`
- START_TIME_KST: 2026-10-26T00:09:57+09:00
- END_TIME_KST: 2026-10-26T00:10:50+09:00
- ELAPSED: PT53S
- TEST_RESULTS: 이번 합성 SQLite 15 passed, 1 skipped, exit 0. pytest 종료 후 Python 프로세스는 없음. PostgreSQL은 이번 게시에서 다시 실행하지 않음. 이전 증거는 2026-10-25T23:41 기록의 일회용 PostgreSQL 15 `127.0.0.1:55441`, `medi010_external_clinical_import`, 합성 1 passed, exit 0, 컨테이너 `eyecare-protocol-009-final-pg` 삭제
- PUSH: origin `feat/clinical-protocol-validation-009`만 일반 푸시. main, 게시된 Phase 009 이력, PC1 통합 브랜치, Draft PR은 변경하지 않음. 새 PR은 만들지 않음
- REMAINING: 서명 승인, ±3일과 ±7일, 방문 6 OSDI 그림, 반올림 자릿수, 단위 문자만 있는 칸의 의미, 연구 귀속, R1 운영 승인, 반복 양식 원본 키. 규칙 활성화, 운영 반입, 배포는 하지 않음
- NEXT_APPROVAL: Phase 010은 시작하지 않음

### 2026-10-25T23:35:00+09:00 — 확정 전 확인

- TASK_ID: PC2-EYECARE-PROTOCOL-009-FINALIZATION-002
- EXECUTION_HOST: SVG-SKLEE (PC2)
- BRANCH: feat/clinical-protocol-validation-009
- BASE_HEAD: 8fba4bfe59ccd28841653cfc55510852e1256ba3
- HEAD: 8fba4bfe59ccd28841653cfc55510852e1256ba3. 작업 트리는 커밋되지 않음
- START_TIME_KST: 2026-10-25T23:35:00+09:00
- END_TIME_KST: 2026-10-25T23:41:49+09:00
- ELAPSED: PT6M49S
- PROTOCOL_SHA256: 39c51490afb38c8b44aebbaaa4a5bb9186e29d29292fb1726138462272fbff91
- EXCEL_SHA256: 1e0ece3a285e2e18fdc4a71999b2a4de680b2dce97ffa0fad0f0a8d773f80dab
- STATUS: CLINICAL_APPROVAL_PENDING. 코드 기본값은 권고 꺼짐
- TEST_RESULTS: 합성 SQLite 15 passed, 1 skipped, exit 0. 일회용 PostgreSQL 15 `127.0.0.1:55441`에서 `medi010_external_clinical_import`까지 올린 뒤 합성 1 passed, exit 0. 컨테이너 `eyecare-protocol-009-final-pg`는 삭제함. pytest 종료 후 Python 프로세스는 없음
- NEXT_APPROVAL: 이 분기 커밋과 푸시는 별도 승인. 게시된 Phase 009, main, PC1 통합 브랜치, Draft PR은 변경하지 않음. Phase 010은 시작하지 않음

## 확인 항목

| 항목 | 현재 근거 | 상태 | 소프트웨어 동작 |
|---|---|---|---|
| 계획서 승인·버전 | 현재 근거 문서는 1.10, 표지 날짜 2026-07-01, 95쪽. 이력은 1.0부터 1.10까지이며 1.10 행은 담당자·관리자 정보 변경이다. 로컬 전문은 1.3과 1.10뿐이다. 2-3쪽 서명란은 비어 있다 | UNRESOLVED | 묶음 ID는 `medi-des-001-v1.10`. EXTRACTED, AWAITING_APPROVAL. ACTIVE 승격은 승인 전 거부 |
| 방문 허용기간 | 1.10의 10.2.3은 방문 3-6에 ±3일. 11.1과 11.2는 ±7일 | CONFLICTING | `window_check`는 모든 방문에서 false. 허용기간 판정 없음 |
| 방문 6 OSDI | 1.10의 11.1·11.2와 부록 1 방문 칸이 방문 1, 2, 3, 4, 6이다. 방문 5는 양쪽 다 없다. 1.3 부록은 방문 1-5만 있어 SOURCE_CONFLICT였다. 1.4-1.9 중 어느 개정인지는 특정하지 않는다 | RESOLVED_BY_V110 | 방문 6 일정 플래그는 true. 방문 5는 false. 허용기간 판정은 하지 않음 |
| OSDI 반올림 | 계산식은 부록 1에 있음. 소수 자릿수와 반올림 규칙은 없음 | UNRESOLVED | 원본 점수를 유지. 차이 0.05 초과 0.5 이내 207행만 권고. 0.5 초과 0행. 0.05 구간은 구현 허용이지 계획서 규칙이 아님 |
| 결측·비숫자 표현 | 아래 표현 분류. 명세 코드 라벨이 아닌 단위 문자와 단위 철자가 있음 | UNRESOLVED | 오류로 바꾸지 않음. 빈 문항을 0이나 해당없음으로 채우지 않음 |
| 워크북 연구 귀속 | 시트명에 연구 코드가 없음. 스크리닝 63행은 `SA-`와 세 자리 형식과 맞음. 외부 이관 기록은 없음 | UNRESOLVED | 워크북만으로 MEDI-DES-001을 확정하지 않음 |
| R1 식별자 | 11.2.1 예시는 SA-001. 무작위 번호 RA-001은 배정 후 식별자 | AWAITING_APPROVAL | `enable_r1` 기본값 false. API도 기본 false. RA 번호를 연결 키로 쓰지 않음 |
| 반복 양식 원본 키 | CM, DE, AE, CT, DS, EX는 계획서에 있으나 안정적인 반복 기록 키가 없음 | AWAITING_APPROVAL | 대상자 단위 스테이징. StudyVisit와 관찰로 올리지 않음. 식별자를 만들지 않음 |

## 원본 표현 분류

읽기 전용으로 명세 Code·라벨 어휘와 계획서 단위 문자만 대조했다. 셀 내용은 출력하지 않았다. 13:03 기록의 "비숫자" 집계는 아래 표현으로 다시 분류하며, 오류 건수가 아니다.

OSDI 문항 OSQ1-OSQ12는 칸마다 빈 값 60, 명세 코드 라벨과 정확히 같은 값 239이다. 다른 문항 문구는 0이다.

OSSCORE 299칸은 점수 단위 문자다. 그중 239칸은 숫자와 그 문자가 함께 있고, 60칸은 그 문자만 있다. 그 60칸과 같은 행의 문항은 비어 있고 OSSUM도 비어 있다. OSNUM 299칸은 개수 단위 문자다. 239칸은 숫자와 함께 있고 60칸은 문자만 있다. 문자만 있는 칸의 임상 의미는 확인 전이다.

TBUT 반복과 평균 8개 항목은 각각 숫자와 초가 함께 있는 칸 238, 초만 있는 칸 61이다. 초만 있는 칸은 평균 계산에 넣지 않았고 오류로 분류하지 않았다. 숫자 3회가 있는 눈의 평균 불일치는 0이다.

쉬르머 표준 칸은 숫자와 `mm` 477칸이다. 오른쪽 61칸과 왼쪽 60칸은 다섯 글자의 라틴 단위로, `mm`으로 시작하고 `min`으로 끝나며 알파벳은 m, i, n뿐이다. 계획서의 `mm/5min`과 철자가 같지 않다. 코 자극 칸 299와 299는 모두 그 다섯 글자 단위다. 방법 추정이나 오류 전환은 하지 않았다. 소수 둘째 자리 이상 권고는 0이다.

## 게시 경계

코드 커밋 후보: `services/clinical_import_parse.py`, `services/clinical_protocol_rules.py`, `services/clinical_import.py`, `tests/test_clinical_import.py`.

문서 커밋 후보: 이 등록부, `CLINICAL-PROTOCOL-RULES-SPEC.md`, `CLINICAL-PROTOCOL-EXCEL-MAPPING.md`, `CLINICAL-IMPORT-VALIDATION-REPORT.md`, `CLINICAL-IMPORT-DATA-DICTIONARY.md`, `EXTERNAL-CLINICAL-DATA-IMPORT-SPEC.md`, `CLINICAL-MODULE-IMPLEMENTATION-ROADMAP.md`.

코드 커밋은 `85ef271b96e36a1a60508d66ff71ae37264235ca`이다. 계획서 PDF, 반출 엑셀, `data/`, 식별 정보, 배정, `timeseries_analysis_summary.json`, 임시 진단 출력은 커밋에서 제외한다.
