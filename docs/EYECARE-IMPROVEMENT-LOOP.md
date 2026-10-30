# 개선 루프

상태: DETECTED → TRIAGED → ACCEPTED/REJECTED → IMPLEMENTED → RETESTED → CLOSED

거절은 REJECTED → CLOSED이며 사유가 필요하다. 그 외 CLOSED는 재분석 증거가 필요하다. 증거 없는 CLOSED는 거부한다.

기록 필드: finding_code, source_analyzer/version, module_id, evidence, severity, reproduction, proposed_correction, decision, fix_ref, test_evidence, reanalysis_outcome, state.

자동 운영 반영은 없다. SVG-Analyzer는 임상 DB를 변경하지 않는다. 수정은 EYECARE 작업 트리에서만 한다.

## Phase 014 사이클 (Clinical Operations UI)

### 2026-10-31 KST reanalysis (adapter 55f7105 disposable image)

| Finding ID | Module | Check | Severity | Disposition | Notes |
| --- | --- | --- | --- | --- | --- |
| ARCH-IFACE-dashboard-c6a76acf | dashboard | unversioned_interface | UNASSESSED | RECOMMENDATION_OPEN | preserved |
| ARCH-IFACE-ecrf_renderer-1370a14b | ecrf_renderer | unversioned_interface | UNASSESSED | RECOMMENDATION_OPEN | preserved |
| ARCH-IFACE-clinical_shell-ef5fd224 | clinical_shell | unversioned_interface | UNASSESSED | RECOMMENDATION_OPEN | new shell; same class |
| ARCH-AUDIT-frontend_security | frontend_security | audit_coverage_gap | UNASSESSED | RECOMMENDATION_OPEN | client security module; server audit elsewhere |
| ARCH-LOSS-57fb48bd61 | alembic | data_loss_path | UNASSESSED | FALSE_POSITIVE_HEURISTIC | medi003 downgrade DELETE heuristic |
| ARCH-MIG-gap | alembic | schema_migration_gap | UNASSESSED | DOCUMENTED_EXCLUSION_OR_RECOMMENDATION | partner / model text gap |

Evidence: `docs/architecture-evidence-014.json` + `docs/architecture-review-014.json`  
Tool image: `ops014-svg-analyzer-arch:55f7105` (built from local SVG-Analyzer @ `55f7105`, does **not** mutate shared `svg-analyzer:0.3.3-ghidra`)  
Modules reviewed: 25. Findings: 6. CLOSED: none (no closure evidence applied).

## Phase 014 초기 disposition (2026-10-30)

| Finding | Module | Disposition | Notes |
| --- | --- | --- | --- |
| ARCH-IFACE-dashboard | dashboard | RECOMMENDATION_OPEN | unversioned UI — preserved |
| ARCH-IFACE-ecrf_renderer | ecrf_renderer | RECOMMENDATION_OPEN | unversioned UI — preserved |
| ARCH-LOSS-medi003 | alembic | FALSE_POSITIVE_HEURISTIC | downgrade DELETE — preserved |
| ARCH-MIG-gap | alembic / partner | DOCUMENTED_EXCLUSION_OR_RECOMMENDATION | partner table gap — preserved |
| clinical_shell unversioned | clinical_shell | RECOMMENDATION_OPEN | SPA shell; same class as dashboard/ecrf_renderer |

Evidence contract: `eyecare-architecture-evidence/1` (tool 014.1). Analyzer adapter ref `55f710569e89f0fee5b86a71da41230a1fcd661f`.

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
