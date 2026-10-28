# 설문 버전과 채점

## 버전

설문 버전 `content_hash`는 발행 시 고정된다. 1.3과 1.10 OSDI 초안은 서로 다른 `QuestionnaireVersion`이다. 1.3 방문은 V1–V5, 1.10은 V1, V2, V3, V4, V6이다. 기존 응답은 원래 `version_id`를 유지한다.

## OSDI 채점

채점 버전: `osdi-medi-des-001-v1`.

공식: `(대답한 문항 점수 합 × 25) / 대답한 문항 수`.

- 점수 범위 0–4
- OSQ6–OSQ12의 해당 없음은 분모에서 제외
- 빈 값은 0으로 바꾸지 않음
- 대답한 문항이 없으면 점수는 null, 상태는 `INCOMPLETE`
- 반올림 자릿수는 UNSPECIFIED
- 계산 결과는 `questionnaire_score_results`에만 두고 원본 `value_json`은 고치지 않음

## 통계

분모는 응답 수다. draft와 final 점수 분포를 나눈다. 서로 다른 설문 버전 점수를 합치지 않는다. 눈가림 배정 비교는 하지 않는다.
