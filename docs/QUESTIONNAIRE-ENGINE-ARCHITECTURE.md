# 설문 엔진 구조

작업 시각: 2026-10-27T11:50:00+09:00 KST (012B 갱신). 호스트 SVG-SKLEE. 브랜치 `feat/protocol-ecrf-autogen-audit-012`, HEAD `a81b410`.

## 012B 검증 요점

- OSDI 초안: 프로토콜 1.3 / 1.10
- 버전 불변, 응답 개정 보존, 원본 응답과 계산 점수 분리
- Not Applicable ≠ blank, Draft/Final 통계 분리
- Study/site 구성원과 clinical lock 강제
- 엔진 경로에서 문항 min/max 검증
- 아키텍처 증거 스키마: `eyecare-architecture-evidence/1`

## 재사용

기존 `questionnaire_definitions`, `questionnaire_versions`, `questionnaire_responses`, `questionnaire_response_items`, `visit_form_assignments`를 그대로 쓴다. 경쟁 저장소를 만들지 않았다.

추가 표:

- `questionnaire_score_results`: 권고 채점. 원본 문항 값을 바꾸지 않는다.
- `improvement_findings`: SVG-Analyzer 개선 제안.

## 흐름

계획서 문서 → `generate_osdi_draft` → 불변 `QuestionnaireVersion` → 응답/문항 → 권고 채점 → 통계.

문항 원문은 `text_policy=SOURCE_BOUND_NOT_REPRODUCED`로 두고 코드와 점수 의미만 저장한다.

## API

- `POST /studies/{id}/questionnaire-drafts`
- `POST /questionnaire-engine/responses`
- `POST /questionnaire-engine/responses/{id}/items`
- `POST /questionnaire-engine/responses/{id}/finalize`
- `POST /questionnaire-engine/responses/{id}/score`
- `GET /studies/{id}/questionnaire-stats`
- `GET /questionnaire`
