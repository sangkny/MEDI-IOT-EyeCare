# 임상 감사 공백

## 2026-10-27T11:50:00+09:00 — 설문·Analyzer 루프 (012B)

해시 체인 대상(link_chain=True):

- questionnaire_drafted
- questionnaire_response_started
- questionnaire_item_saved
- questionnaire_response_finalized
- questionnaire_scored
- protocol_registered / ecrf_generated 계열

체인 밖(사건만 또는 미구현):

- clinical_query 수명주기
- data_lock / unlock
- clinical_import
- electronic_signature (MISSING)
- data_export (MISSING)
- 역할 변경
- 외부 감사 봉인

전자서명 준수나 외부 봉인을 주장하지 않는다.

## 2026-10-27T11:19:52+09:00 — 설문 엔진

| 사건 | 상태 |
| --- | --- |
| 설문 초안 생성 | 체인 연결 |
| 응답 시작, 문항 저장, 확정 | 체인 연결. 값은 `value_protected` |
| 권고 채점 | 체인 연결. 원본 응답 값은 변경하지 않음 |
| 계획서 등록/eCRF | 체인 연결 |
| 질의, 품질, 가져오기, 잠금 | 기존 `_audit`. 체인 표가 있는 앱 세션에서 연결 |
| 전자서명, 내보내기 | MISSING |
| 외부 봉인 | 없음. 해시 체인은 DB 내부 변조 탐지다 |

모든 EYECARE 사건이 해시 체인에 있다고 주장하지 않는다.

# 이전 분석

## 이번 작업에서 닫은 항목

계획서 등록, 초안 생성, 검토, 모의 승인, 스키마 활성화, eCRF 입력은 같은 세션에서 `clinical_audit_events`와 `audit_event_chains`에 기록한다. 체인에는 사건 ID, 역할, 계획서 버전, 스키마 버전, 상관 ID, 이전 해시, 사건 해시가 있다. 시각과 행위자와 대상은 기존 감사 행에 있다.

SQLite 테스트는 체인 행의 UPDATE를 트리거로 거부한다. `medi011`은 PostgreSQL에서 기존 `reject_append_only_clinical_history` 함수로 같은 표를 보호한다.

## 아직 체인에 없는 기존 사건

질의 수명주기, 잠금과 해제, 전자서명, 가져오기, 역할 변경, 내보내기는 기존 `ClinicalAuditEvent`에 남을 수 있다. 그 행에는 계획서 버전과 해시 체인이 없다. 이번 개정은 그 쓰기 경로를 다시 구현하지 않았다.

전자서명의 법적 효력, 보관 기간, 외부 봉인은 구현하지 않았다. 체인 해시는 같은 데이터베이스 안의 변조 탐지이며 독립된 보관 저장소가 아니다.

일반 로그에는 측정값을 쓰지 않는다. 입력 감사 페이로드는 필드 ID와 개정 번호와 `value_protected`만 가진다.
