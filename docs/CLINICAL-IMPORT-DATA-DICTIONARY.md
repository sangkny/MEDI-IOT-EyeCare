# 외부 반출 데이터 사전

로컬 `data/`의 Excel 1건을 읽기 전용으로 해석했다. 바이트 크기는 369628이다. 워크시트는 34개이며 명세 17개와 데이터 17개가 쌍이다. 셀 값, 식별자, 측정값은 적지 않는다. 원본 파일은 Git에서 제외된다.

## 진행 기록

### 2026-10-25T09:32:46+09:00 — 미해결 매핑을 게시 기록에 고정

- TASK_ID: PC2-EYECARE-PHASE009-PUBLICATION-001
- EXECUTION_HOST: SVG-SKLEE
- BRANCH: feat/external-clinical-import-009
- HEAD_BEFORE: 79848a924515ee72e8ed3f95af444a6aab60f750
- HEAD_AFTER: 이 게시 커밋
- START_TIME_KST: 2026-10-25T09:31:42+09:00
- END_TIME_KST: 2026-10-25T09:32:46+09:00
- ELAPSED: PT1M4S
- REMAINING_ISSUES: A 696행 보류, B 연구·사이트 미확인, C 단위 미확인, D OSDI 코드표 없음, E MEDI-DES-001 미귀속

### 2026-10-25T01:01:03+09:00 — 식별자 제거 사전

- TASK_ID: PC2-EYECARE-CLINICAL-IMPORT-009
- EXECUTION_HOST: SVG-SKLEE
- BRANCH: feat/external-clinical-import-009
- HEAD_BEFORE: 79848a924515ee72e8ed3f95af444a6aab60f750
- START_TIME_KST: 2026-10-25T00:45:00+09:00
- END_TIME_KST: 2026-10-25T01:01:03+09:00
- ELAPSED: PT16M3S
- REMAINING_ISSUES: 연구 코드와 사이트 코드는 파일에 없음

## 확인된 구조

명세 헤더는 `Domain`, `Item ID`, `Item Label`, `Code`, `Layout`, `Type`, `Required`다. 각 데이터 시트의 항목 라벨은 직전 명세와 오프셋 5에서 불일치 0으로 맞는다.

앞 5개 열은 `작성일자`, `병록번호`, `이름`, `성별`, `나이`다. `병록번호`와 `이름`은 직접 식별자로 보고 해시만 남긴다. 정규 대상자 키로 쓰지 않는다.

## 확정 매핑

| 원본 | 정규 대상 | 근거 |
|---|---|---|
| `SUBJID` 스크리닝 번호 | `StudySubject.subject_code` | 명세 항목 ID. 스크리닝 시트에만 있음 |
| `SVDAT` 방문일 | `StudyVisit.occurred_on` | 명세 항목 ID. 빈 값은 만들지 않음 |
| 시트명의 `V숫자 (` | `StudyVisit.visit_code` | `_V1.1` 양식 버전은 방문이 아님 |
| `TBODORS1-3`, `TBOSORS1-3` | 관찰 `TBUT`, 좌우, 반복 | 항목 ID와 좌우 시행 항목의 인접 |
| `TBODORSAV`, `TBOSORSAV` | 관찰 `TBUT` 보고 평균 | 같은 눈 블록의 평균 항목 |
| `STODORS`, `STOSORS` | 관찰 `SCHIRMER` | 항목 ID |
| `OSQ1-12` | 설문 `OSDI` 초안 문항 | 명세 라벨 |
| `OSSCORE` | 관찰 `OSDI_SCORE` | 명세 항목 ID |

단위는 명세에 없어 UNRESOLVED다. 관찰 `unit`은 비운다.

## 미해결

- 연구 코드와 사이트 코드는 파일에 없다. `MEDI-DES-001` 문자열도 없다.
- V2 이후 명세에는 `SUBJID`가 없다. 이름이나 병록번호로 연결하지 않는다.
- `RN` 도메인과 무작위 배정 라벨은 값을 저장하지 않는다.
- OSDI 문항의 코드표와 쉬르머 텍스트 토큰은 확정하지 않았다.
- 이상사례, 병용약, 치료 시트는 스테이징만 하고 정규 관찰로 만들지 않는다.
- 같은 방문 코드의 데이터 시트가 둘인 경우가 있다. 목적 차이는 UNRESOLVED다.
