# 계획서와 반출 명세의 대응

식별자와 측정값은 적지 않는다. 엑셀은 읽기만 했다.

## 진행 기록

### 2026-10-26T15:51:33+09:00 — 1.10 대응 게시

- TASK_ID: PC2-EYECARE-PROTOCOL-V110-PUBLICATION-004
- EXECUTION_HOST: SVG-SKLEE (PC2)
- BRANCH: feat/clinical-protocol-validation-009
- CODE_COMMIT: 574b9527fbed211d6ef2f75699888f8db58f50d6
- DOCS_COMMIT: 이 문서 커밋
- START_TIME_KST: 2026-10-26T15:51:33+09:00
- END_TIME_KST: 2026-10-26T15:53:37+09:00
- ELAPSED: PT2M4S
- PROTOCOL_SHA256: 9e24fcedbd869e4e2b88d8b33e32acf617d4fd541199c78cd4c75d6444e2ac44
- TEST_RESULTS: 합성 SQLite 15 passed, 1 skipped, exit 0. 일회용 PostgreSQL 15 합성 1 passed, exit 0
- NEXT_APPROVAL: 원본 PDF와 엑셀은 커밋하지 않음. Phase 010은 시작하지 않음

### 2026-10-26T15:01:00+09:00 — 계획서 1.10 출처

- TASK_ID: 로컬 계획서 1.10 반영
- EXECUTION_HOST: SVG-SKLEE (PC2)
- BRANCH: feat/clinical-protocol-validation-009
- START_TIME_KST: 2026-10-26T15:01:00+09:00
- END_TIME_KST: 2026-10-26T15:04:39+09:00
- ELAPSED: PT3M39S
- PROTOCOL_SHA256: 9e24fcedbd869e4e2b88d8b33e32acf617d4fd541199c78cd4c75d6444e2ac44
- TEST_RESULTS: 합성 SQLite 15 passed, 1 skipped, exit 0. PostgreSQL은 다시 실행하지 않음
- NEXT_APPROVAL: 원본 PDF는 커밋하지 않음. Phase 010은 시작하지 않음

### 2026-10-26T00:09:57+09:00 — 표현 분류 게시

- TASK_ID: PC2-EYECARE-PROTOCOL009-PUBLICATION-003
- EXECUTION_HOST: SVG-SKLEE (PC2)
- BRANCH: feat/clinical-protocol-validation-009
- CODE_COMMIT: 85ef271b96e36a1a60508d66ff71ae37264235ca
- DOCS_COMMIT: 이 문서 커밋
- START_TIME_KST: 2026-10-26T00:09:57+09:00
- END_TIME_KST: 2026-10-26T00:10:50+09:00
- ELAPSED: PT53S
- TEST_RESULTS: 이번 합성 SQLite 15 passed, 1 skipped, exit 0. PostgreSQL은 다시 실행하지 않음
- NEXT_APPROVAL: 원본 엑셀과 계획서 PDF는 커밋하지 않음. Phase 010은 시작하지 않음

### 2026-10-25T23:35:00+09:00 — 표현 재분류

- TASK_ID: PC2-EYECARE-PROTOCOL-009-FINALIZATION-002
- EXECUTION_HOST: SVG-SKLEE (PC2)
- BRANCH: feat/clinical-protocol-validation-009
- HEAD: 8fba4bfe59ccd28841653cfc55510852e1256ba3
- START_TIME_KST: 2026-10-25T23:35:00+09:00
- END_TIME_KST: 2026-10-25T23:41:49+09:00
- ELAPSED: PT6M49S
- CLASSIFICATION: 아래 13:03 표의 비숫자 칸은 단위 문자 또는 `mm`과 `min`이 붙은 철자다. 측정값은 출력하지 않았고 오류로 바꾸지 않았다
- TEST_RESULTS: 합성 SQLite 15 passed, 1 skipped, exit 0. 일회용 PostgreSQL 15 `127.0.0.1:55441`에서 `medi010_external_clinical_import`까지 올린 뒤 합성 1 passed, exit 0. 컨테이너 `eyecare-protocol-009-final-pg`는 삭제함. pytest 종료 후 Python 프로세스는 없음
- NEXT_APPROVAL: `CLINICAL-CLARIFICATION-REGISTER.md`. 커밋과 푸시 없음

### 2026-10-25T13:03:02+09:00 — 출처 비교

- TASK_ID: PC2-EYECARE-PROTOCOL-VALIDATION-009
- EXECUTION_HOST: SVG-SKLEE (PC2)
- BRANCH: feat/clinical-protocol-validation-009
- BASE_HEAD: 8fba4bfe59ccd28841653cfc55510852e1256ba3
- START_TIME_KST: 2026-10-25T13:03:02+09:00
- END_TIME_KST: 2026-10-25T13:13:30+09:00
- ELAPSED: PT10M28S
- EXCEL: `20260301~20261019_1792368042_form_data.xlsx`
- EXCEL_SHA256: 1e0ece3a285e2e18fdc4a71999b2a4de680b2dce97ffa0fad0f0a8d773f80dab
- EXCEL_BYTES: 369628
- PROTOCOL_SHA256: 39c51490afb38c8b44aebbaaa4a5bb9186e29d29292fb1726138462272fbff91
- SVG_ANALYZER: 사용하지 않음. REA는 계획서와 스프레드시트 해석 기능이 없다
- REAL_EXPORT: 읽기 전용 집계만 수행. 일회용 DB에 원본 행을 넣지 않음

## 출처 상태

로컬에는 계획서 1.3 전문, 1.3 변경대비표, 계획서 1.10 전문, 반출 엑셀이 있다. 현재 규칙 근거는 1.10이다. 1.4부터 1.9까지의 전문은 없다. 별도 OSDI 설문 파일과 승인된 별첨 1-4 본문, eCRF 작성지침은 없다. OSDI 문항과 계산식은 1.10 부록 1 그림에 있다. 서명란은 비어 있어 승인 상태는 UNRESOLVED다.

1.10의 10.2.3은 방문 3-6을 ±3일로 적고, 11.1과 11.2는 ±7일이다. 같은 문서 안의 충돌이므로 하나를 고르지 않는다. 부록 1 방문 칸은 방문 1, 2, 3, 4, 6이라 일정표의 OSDI와 같다.

워크북이 MEDI-DES-001이라는 운영 귀속은 확정하지 않는다. 시트 제목의 방문 간격, 스크리닝 번호 형식, MEDI-EYE 시트 이름이 계획서와 같은 방향이지만, 반출 명세에 연구 코드가 없고 서명된 이관 기록도 없다.

## 증거 행렬

| 임상 요구 | 계획서 | 엑셀 항목 | 검증 | 상태 | 남은 문제 |
|---|---|---|---|---|---|
| OSDI 12문항, 0-4점 | 부록 1 | OSQ1-OSQ12 Code 열 | 비어 있지 않은 2,868칸이 명세 라벨과 일치. 다른 값 0 | CROSS_SOURCE_CONFIRMED | 문항 문구의 저작권 원문 재게재는 하지 않음 |
| 해당 없음은 0이 아님 | 부록 1, 6-12번 | OSQ6-12의 `해당없음` | 디코더가 점수에서 제외 | SOURCE_CONFIRMED | 저장값이 라벨이 아니면 기존 미해결 분류를 유지 |
| OSDI = 합 x 25 / 응답 수 | 부록 1 식 | OSSUM, OSNUM, OSSCORE | 숫자로 읽힌 239행은 0.5 이내. 불일치 0. 0.05 초과 207행은 반올림 권고 | CROSS_SOURCE_CONFIRMED | 60행의 점수 칸은 숫자가 아님. 반올림 자릿수는 계획서에 없음 |
| TBUT 3회 평균, 초 | 1.10 p.53, 주석 13 | TBODORS1-3, TBOSORS1-3, 평균 | 숫자 3회가 있는 476눈은 평균과 0.05 이내. 불일치 0 | CROSS_SOURCE_CONFIRMED | 초만 있는 칸은 오류로 세지 않음. 결측 반복의 처리 문장은 없음 |
| 쉬르머 비마취 5분, mm/5min, 소수 1자리 | 1.10 p.55, 주석 14 | STODORS, STOSORS | 단위 메타데이터만 규칙에 기록. 477칸은 숫자+mm | SOURCE_CONFIRMED | 121칸은 `mm`과 `min`이 이어진 철자. 코 자극 칸의 방법은 UNRESOLVED |
| 방문 1 스크리닝, 2 기저, 3 4주, 4 8주, 5 10주, 6 12주 | 1.10 11.1, 11.2 | 시트 제목 V1-V6. `_V1.1`은 양식 버전 | V5에는 TBUT, OSDI, 쉬르머가 없고 V1-V4와 V6에는 있음 | CROSS_SOURCE_CONFIRMED | 방문 4의 MEDI-EYE 치료는 표와 11.2.4 절차가 달라 UNRESOLVED |
| 허용기간 | 1.10 10.2.3 ±3일, 11.1/11.2 ±7일 | 시트 제목은 ±7일 | 허용기간 판정을 구현하지 않음 | CONFLICTING | 1.10 안에서도 두 문장이 공존 |
| 스크리닝 번호 SA-001 | 11.2.1 | SUBJID | 스크리닝 63행이 `SA-`와 세 자리 형식 | CROSS_SOURCE_CONFIRMED | 연구 귀속의 외부 이관 증거는 없음. R1은 기본 꺼짐 |
| 병용약, 이상사례, 의료기기 결함, 치료 | 10.3, 11.2, 15장 | CM, DE, AE, CT, DS, EX | 대상자 단위 스테이징 유지. 안정 반복 키 없음 | SOURCE_CONFIRMED | 정규 모델과 원본 기록 키는 AWAITING_APPROVAL |
| 눈가림 | 10.1 | RN과 배정 라벨 | 값을 저장하지 않음 | SOURCE_CONFIRMED | 배정을 추정하지 않음 |

1.10 부록 1의 방문 칸은 방문 1, 2, 3, 4, 6이다. 일정표의 OSDI도 방문 5가 비어 있고 방문 6이 있다. 상태는 RESOLVED_BY_V110이다. 1.3 부록은 방문 1-5만 있었다. 1.4-1.9 중 어느 개정인지는 특정하지 않는다.

## 읽기 전용 집계

구현된 권고 함수를 원본에 읽기 전용으로 적용했다. 행 759. OSDI 반올림 권고 207. 점수 불일치 0. TBUT 평균 불일치 0. 쉬르머 자릿수 권고 0. 값은 출력하지 않았다.
