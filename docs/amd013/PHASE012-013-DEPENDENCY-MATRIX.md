# Phase 012 / 013 의존·통합 매트릭스

시각: 2026-10-29T07:29:19+09:00 KST 갱신  
Phase 012 published HEAD: `9ab5b0df385a8ddd4e8974f1090cd19075b7bb94` (`feat/protocol-ecrf-autogen-audit-012`)  
통합 후보 worktree: `MEDI-IOT-EyeCare-amd013-integ` @ Phase 012 + AMD-only overlay  
원본 dirty worktree `MEDI-IOT-EyeCare-amd-013` 는 파괴적 rebase 없이 보존

| 구성요소 | ecrf-012 | amd-013 | 의존 | 비고 |
| --- | --- | --- | --- | --- |
| medi011/medi012 migrations | 있음(미커밋) | 동일 복사본 | 013 → 012 모델 | SHA 동일 |
| clinical_support models | 있음 | SHA 동일 | 013 필수 | ProtocolDocument, Ecrf*, Audit chain |
| protocol_ecrf 엔진 | DES catalog | DES + AMD unresolved wiring | 013이 012 엔진 확장 | 파일 해시 다름 |
| questionnaire_engine | 있음 | 복사본 | AMD는 미연결 | OSDI를 AMD에 넣지 않음 |
| architecture_evidence `/1` | 있음 | 확장(multi_protocol_catalogs) | Analyzer 계약 공유 | |
| amd_protocol_catalog | **없음** | 있음 | 013 전용 | 012에 디렉터리 통째 복사 금지 |
| amd_stats_poc / findings | **없음** | 있음 | 013 전용 | |
| multi-protocol tests | **없음** | 있음 | 013 | |

## 결론

AMD Phase 013은 **미커밋 Phase 012** Protocol/eCRF/Audit/Evidence 기능에 의존한다.  
012가 게시되기 전에 013만 단독 publish하면 깨진다.

권장 게시 순서:

1. Phase 012 (medi011/012, protocol/questionnaire/audit/evidence)
2. Phase 013 AMD catalog + findings + multi-protocol tests
3. (이후) 운영 활성화 작업 — 이번 범위 밖
