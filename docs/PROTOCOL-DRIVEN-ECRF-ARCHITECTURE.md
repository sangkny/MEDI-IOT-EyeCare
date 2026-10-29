# 계획서 기반 eCRF 구조

양식 카탈로그는 계획서 식별자별로 고른다. `MEDI-DES-001`이 아닌 식별자는 그 연구의 등록 카탈로그만 사용한다. 카탈로그가 없으면 필드 없는 `NO_CATALOG` 제안만 만든다.

MEDI-DES-001에서 필드가 있는 양식은 스크리닝 `SUBJID`, TBUT 반복과 평균, Schirmer, OSDI 점수와 OSQ1–OSQ12이다. OSQ6–OSQ12는 해당 없음 제안만 허용한다. 점수 0–4는 제안 범위이고 강제하지 않는다. 방문 평가의 FCSS와 LGCSS, 선정/제외, 병력, CM, CT, AE, DE, EX, DS는 출처에 문항 키나 안정 반복 키가 없어 양식 이름만 제안한다. 초안은 `proposal`이며 규칙 묶음을 ACTIVE로 바꾸지 않는다.

감사 체인은 `link_chain`이 참이거나 세션이 `link_audit_chain`일 때 같은 트랜잭션에 붙는다. `get_db`는 `audit_event_chains`가 있을 때만 그 플래그를 켠다. 외부 봉인은 없다.

# 이전 구조

작업 트리 `feat/protocol-ecrf-autogen-audit-012`의 기준은 `a81b410f5bbdc4ac1739c99b4f97eb29187ac28e`다. 커밋하지 않았다.

## 재사용한 기능

| 영역 | 상태 | 근거 |
| --- | --- | --- |
| 관찰, 개정, 사이트 구성원 | VERIFIED | `services/clinical_records.py` |
| 설문 정의와 응답 | VERIFIED | `questionnaire_*` 모델. 이번 초안은 그 표를 덮어쓰지 않는다. |
| 질의, 품질, 잠금 | VERIFIED | 기존 서비스. 잠긴 방문은 새 입력을 거부한다. |
| 감사 행과 해시 | VERIFIED | `ClinicalAuditEvent`. PostgreSQL 추가 전용 트리거는 `medi009`에 있다. |
| 가져오기와 계획서 권고 | VERIFIED | `clinical_import.py`, `clinical_protocol_rules.py`. 규칙은 ACTIVE가 아니다. |
| 증례 대시보드 | VERIFIED | 집계 JSON은 유지하고 계획서 화면으로 이동하는 단추만 추가했다. |
| LLM 제안 | BLOCKED | 로컬 `127.0.0.1:1234`가 응답하지 않았다. 외부 모델로 계획서 본문을 보내지 않았다. |

## 추가한 경계

`protocol_documents`는 원본 존재, 추출, 검토, 승인, 운영 활성을 따로 둔다. 개발 승인은 `SIMULATED_APPROVAL`이며 `simulated_approval`이 참이다. 실제 서명 기록을 만들지 않는다.

`ecrf_schema_versions.definition_json`은 생성 시 해시로 고정한다. 활성화는 `status`만 `ACTIVE`로 바꾼다.

`ecrf_entries`는 계획서 버전, 스키마 ID, 논리 필드 ID, 반복 번호, 개정을 함께 저장한다. 값이 바뀌면 다음 개정 행을 추가한다.

`audit_event_chains`는 기존 감사 행에 역할, 계획서 버전, 스키마 ID, 상관 ID, 이전 해시를 붙인다. 페이로드에는 측정값 대신 `value_protected`만 둔다.

## 화면

`GET /protocol-ecrf`가 `static/protocol-ecrf/index.html`을 제공한다. 데이터는 `GET /api/v1/clinical-support/studies/{study_id}/ecrf-schemas/{schema_id}`이며 사이트 구성원만 읽는다.
