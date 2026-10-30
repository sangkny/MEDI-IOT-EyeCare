# EYECARE 모듈 레지스트리

논리 모듈이다. 별도 네트워크 서비스로 쪼개지 않았다.

| Module ID | Owner path | Entities | Depends on | State |
| --- | --- | --- | --- | --- |
| protocol_registry | services/protocol_ecrf.py | protocol_documents | clinical_records | IMPLEMENTED |
| protocol_extraction | services/clinical_protocol_rules.py | none | none | IMPLEMENTED |
| amendment_engine | services/protocol_ecrf.py | none (writes via ecrf_schema ownership) | protocol_registry | IMPLEMENTED |
| ecrf_schema | services/protocol_ecrf.py | ecrf_schema_versions, ecrf_entries | protocol_extraction | IMPLEMENTED |
| ecrf_renderer | static/protocol-ecrf | none | ecrf_schema | IMPLEMENTED |
| questionnaire_definition | services/questionnaire_engine.py | questionnaire_definitions/versions | protocol_extraction | IMPLEMENTED |
| questionnaire_response | services/clinical_records.py | questionnaire_responses/items | questionnaire_definition | IMPLEMENTED |
| questionnaire_scoring | services/questionnaire_engine.py | questionnaire_score_results | questionnaire_response | IMPLEMENTED |
| questionnaire_analytics | services/questionnaire_engine.py | none | questionnaire_scoring | IMPLEMENTED |
| clinical_records | services/clinical_records.py | clinical_observations | audit_trail | IMPLEMENTED |
| data_quality | services/clinical_quality.py | data_quality_* | clinical_records | IMPLEMENTED |
| clinical_query | services/clinical_queries.py | clinical_queries | clinical_records | IMPLEMENTED |
| audit_trail | services/clinical_records.py | clinical_audit_events, audit_event_chains | none | PARTIAL |
| dashboard | services/clinical_case_dashboard.py | none | clinical_records | IMPLEMENTED |
| import_reconciliation | services/clinical_import.py | import_* | clinical_records | IMPLEMENTED |
| analyzer_integration | services/architecture_evidence.py | improvement_findings | questionnaire_definition | IMPLEMENTED |
| auth_ui | static/clinical-ops/ops-session.js, api/clinical_ops.py | none | auth token | IMPLEMENTED |
| clinical_shell | static/clinical-ops | none | auth_ui, study_scope | IMPLEMENTED |
| audit_viewer | static/clinical-ops + ops/audits | none (read) | audit_trail | IMPLEMENTED |
| query_workspace | static/clinical-ops | none | clinical_query | IMPLEMENTED |
| lock_workspace | static/clinical-ops | none | clinical_records locks | IMPLEMENTED |
| study_scope | static/clinical-ops + ops/session | none | clinical_records | IMPLEMENTED |
| frontend_security | ops-session.js | none | auth_ui | IMPLEMENTED |
| multi_protocol_catalogs | services/amd_protocol_catalog.py | none | protocol_registry | IMPLEMENTED |

순환 의존은 없다. `audit_trail`은 공통 하위에 있다. 전자서명과 내보내기 생산자는 아직 없다. Clinical Operations UI는 마이크로서비스가 아니다.
