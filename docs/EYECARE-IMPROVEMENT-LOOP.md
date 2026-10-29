# 개선 루프

상태: DETECTED → TRIAGED → ACCEPTED/REJECTED → IMPLEMENTED → RETESTED → CLOSED

거절은 REJECTED → CLOSED이며 사유가 필요하다. 그 외 CLOSED는 재분석 증거가 필요하다. 증거 없는 CLOSED는 거부한다.

기록 필드: finding_code, source_analyzer/version, module_id, evidence, severity, reproduction, proposed_correction, decision, fix_ref, test_evidence, reanalysis_outcome, state.

자동 운영 반영은 없다. SVG-Analyzer는 임상 DB를 변경하지 않는다. 수정은 EYECARE 작업 트리에서만 한다.

## 첫 사이클 (012B)

| 항목 | 값 |
| --- | --- |
| Analyzer | svg-analyzer 0.3.3 |
| Ontology | architecture_review 1.3.0 |
| Evidence schema | eyecare-architecture-evidence/1 |
| Before findings | 5 |
| Selected | ARCH-DB-4a39d6a5 (confirmed_defect, db_ownership_conflict on ecrf_schema_versions) |
| Correction | amendment_engine.db_owns 에서 ecrf_schema_versions 제거. 소유는 ecrf_schema 단독 |
| After findings | 4 |
| Outcome | ARCH-DB-4a39d6a5 RESOLVED by reanalysis |
| Left open | ARCH-IFACE-dashboard, ARCH-IFACE-ecrf_renderer, ARCH-LOSS-medi003, ARCH-MIG-gap |
