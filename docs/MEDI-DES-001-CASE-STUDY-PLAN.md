# MEDI-DES-001 사례 검증 계획

목적은 가져오기 충실도를 보는 것이다. 치료 효과를 판단하지 않는다. 배정을 추정하지 않는다.

## 진행 기록

### 2026-10-25T09:32:46+09:00 — 사례 한계를 유지한 게시

- TASK_ID: PC2-EYECARE-PHASE009-PUBLICATION-001
- EXECUTION_HOST: SVG-SKLEE
- BRANCH: feat/external-clinical-import-009
- HEAD_BEFORE: 79848a924515ee72e8ed3f95af444a6aab60f750
- HEAD_AFTER: 이 게시 커밋
- START_TIME_KST: 2026-10-25T09:31:42+09:00
- END_TIME_KST: 2026-10-25T09:32:46+09:00
- ELAPSED: PT1M4S
- REMAINING_ISSUES: 이번 게시에서 실데이터 사례를 다시 실행하지 않음. E 연구 귀속은 미해결

### 2026-10-25T01:01:03+09:00 — 사례 범위

- TASK_ID: PC2-EYECARE-CLINICAL-IMPORT-009
- EXECUTION_HOST: SVG-SKLEE
- BRANCH: feat/external-clinical-import-009
- START_TIME_KST: 2026-10-25T00:45:00+09:00
- END_TIME_KST: 2026-10-25T01:01:03+09:00
- ELAPSED: PT16M3S
- REMAINING_ISSUES: 파일만으로 연구 코드를 확인할 수 없음

로컬 반출 1건을 호출자가 지정한 연구 문맥으로만 읽는다. 파일 내부에서 `MEDI-DES-001`을 찾지 못했으므로 연구 귀속은 UNRESOLVED다. DeeVo에는 접속하지 않는다. 원본 파일은 수정하지 않는다.

집계만 `CLINICAL-IMPORT-VALIDATION-REPORT.md`에 남긴다. 대상자 목록과 측정값은 문서에 쓰지 않는다.

방문 창, 정상 범위, 효능 기준은 승인 원문이 생기기 전에 만들지 않는다.
