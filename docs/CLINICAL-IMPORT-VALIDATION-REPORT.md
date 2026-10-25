# 외부 반출 검증 보고

식별자와 측정값은 포함하지 않는다. 원본 워크북은 수정하지 않았고 Git에 올리지 않는다.

## 진행 기록

### 2026-10-25T09:32:46+09:00 — Phase 009 게시

- TASK_ID: PC2-EYECARE-PHASE009-PUBLICATION-001
- EXECUTION_HOST: SVG-SKLEE
- PC_ROLE: PC2
- REPOSITORY: MEDI-IOT-EyeCare
- BRANCH: feat/external-clinical-import-009
- BASELINE_HEAD: 79848a924515ee72e8ed3f95af444a6aab60f750
- HEAD_BEFORE: 79848a924515ee72e8ed3f95af444a6aab60f750
- HEAD_AFTER: 이 게시 커밋
- START_TIME_KST: 2026-10-25T09:31:42+09:00
- END_TIME_KST: 2026-10-25T09:32:46+09:00
- ELAPSED: PT1M4S
- COMMIT: `feat: implement external clinical data import foundation`
- PUSH: origin `feat/external-clinical-import-009`만. force push와 main 병합 없음
- TEST_RESULTS: 이번 합성 SQLite 8 passed, 1 skipped, exit 0. 이번 일회용 PostgreSQL 15 `127.0.0.1:55438`에서 `medi010_external_clinical_import` upgrade 후 합성 가져오기 1 passed, exit 0. 컨테이너 삭제. 실데이터 사례는 다시 실행하지 않음
- REMAINING_ISSUES: 아래 A–E는 미해결 매핑 의존성이다. 보류 행은 가져온 것이 아니다
- NEXT_APPROVAL: PC1 통합은 이 게시에서 만들지 않음. Phase 010은 시작하지 않음

### 2026-10-25T01:01:03+09:00 — 일회용 DB 집계

- TASK_ID: PC2-EYECARE-CLINICAL-IMPORT-009
- EXECUTION_HOST: SVG-SKLEE
- PC_ROLE: PC2
- BRANCH: feat/external-clinical-import-009
- HEAD_BEFORE: 79848a924515ee72e8ed3f95af444a6aab60f750
- HEAD_AFTER: 79848a924515ee72e8ed3f95af444a6aab60f750
- START_TIME_KST: 2026-10-25T00:45:00+09:00
- END_TIME_KST: 2026-10-25T01:01:03+09:00
- ELAPSED: PT16M3S
- DATABASE: 일회용 PostgreSQL 15 `127.0.0.1:55437`, 이름 없는 데이터 디렉터리. 집계 후 컨테이너 삭제
- TEST_RESULTS: 합성 SQLite 8 passed, 1 skipped, exit 0. 같은 일회용 DB에서 합성 가져오기 1 passed
- REMAINING_ISSUES: 연구 코드 미확인. V2 이후 대상자 키 미해결. 커밋 없음

## 구조 집계

- 데이터 시트 17개, 정렬 확인 17개, 데이터 행 759개
- 스크리닝 번호가 있는 행에서 서로 다른 대상자 63명, 대상자-방문 쌍 63개
- 방문 코드별 행 수: V1 63, V2 60, V3 60, V4 60, V5 60, V6 56
- 방문일 결측 0, 방문일 해석 실패 0, 스크리닝 번호 결측 0
- 배정 칸 180개는 값을 저장하지 않음
- 코드표가 없어 `NEEDS_HUMAN_REVIEW`로만 분류한 칸 4064개. 입력 오류로 단정하지 않음

## 일회용 DB에 반영한 정규 행

스크리닝 시트만 `SUBJID`가 있어 정규 반영됐다.

- 대상자 63, Visit 63, 초안 관찰 819, 확정 관찰 0, OSDI 초안 응답 63
- 검증 분류 1008, 값 불일치 0
- 스테이징 상태: 반영 63행, 매핑 보류 696행
- 자동 확정과 자동 잠금은 하지 않음

V2 이후 시트는 대상자 항목이 없어 이름이나 병록번호로 잇지 않고 보류했다. 이 워크북이 MEDI-DES-001이라는 문구는 파일에 없다.

## 미해결 매핑 의존성

아래 항목은 해결되지 않았다. 이름, 병록번호, 그 밖의 추정으로 대상자를 연결하지 않는다. 보류된 696행은 정규 임상 행으로 가져온 것이 아니다.

- A. 승인된 종단 대상자 키가 없는 696행은 보류다.
- B. 연구와 사이트 귀속은 파일에서 확인되지 않았다.
- C. TBUT와 쉬르머의 측정 단위는 명세에 없다.
- D. OSDI 코드표의 권위 있는 원문이 없다.
- E. MEDI-DES-001 귀속은 워크북만으로 성립하지 않는다.
