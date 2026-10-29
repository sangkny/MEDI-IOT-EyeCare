# 설문 ↔ SVG-Analyzer 첫 사이클 증거

시각: 2026-10-27T12:11:13+09:00 KST  
호스트: SVG-SKLEE (PC2)  
작업 트리: `C:\Office_Automation\MEDI-IOT-EyeCare-ecrf-012`  
브랜치: `feat/protocol-ecrf-autogen-audit-012`  
HEAD: `a81b410f5bbdc4ac1739c99b4f97eb29187ac28e` (미커밋 Phase 012/012A/012B 작업 보존)

## 환경

| 항목 | 값 |
| --- | --- |
| Port Registry | `\\MEDIIOT-SKLEE\idea-collection\projects\PORT-ALLOCATION.md` |
| Port Registry SHA-256 | `5D97108C4BB335CFD3653EC32D9B7C91302B34F6947F38BEE0F4C9F822FED734` |
| WSL2 / Docker | 사용. 앱·PG·Redis는 `ecrf012b-net` 내부만 |
| 호스트 추가 게시 | 없음 (8001/8772/55444 유지) |
| LLM :1234 | LLM_UNAVAILABLE |
| Browser | BROWSER_NOT_VERIFIED (호스트 포트 미게시, 컨테이너 내부 JWT API 검증) |

## Analyzer

| 항목 | 값 |
| --- | --- |
| Tool | svg-analyzer 0.3.3 |
| Ontology | architecture_review 1.3.0 |
| Evidence schema | `eyecare-architecture-evidence/1` |
| Legacy draft | `eyecare-architecture-evidence/v1` REJECTED |
| Evidence file | `docs/architecture-evidence.json` |
| Before report | `docs/architecture-review-before.json` (5 findings) |
| After report | `docs/architecture-review-after.json` (4 findings) |

## Finding 요약

| ID | Class | Before | After |
| --- | --- | --- | --- |
| ARCH-DB-4a39d6a5 | confirmed_defect (db_ownership_conflict) | OPEN | RESOLVED |
| ARCH-IFACE-dashboard-c6a76acf | architectural_recommendation | OPEN | OPEN |
| ARCH-IFACE-ecrf_renderer-1370a14b | architectural_recommendation | OPEN | OPEN |
| ARCH-LOSS-57fb48bd61 | architectural_recommendation | OPEN | OPEN |
| ARCH-MIG-gap | architectural_recommendation | OPEN | OPEN |

## 선택 수정

- Finding: ARCH-DB-4a39d6a5
- 원인: `amendment_engine` 과 `ecrf_schema` 가 동시에 `ecrf_schema_versions` 소유 선언
- 변경: `services/architecture_evidence.py` 에서 amendment_engine.db_owns 를 비움. 소유는 ecrf_schema 단독
- 임상 DB/기록 변경 없음. SVG-Analyzer 저장소 변경 없음

## 시험

- Windows SQLite: questionnaire+protocol 10 passed
- Docker JWT 흐름: JWT_FLOW_OK (401/403/교차사이트 포함)
- Docker pytest: **79 passed**, exit 0 (일회용 `eyecare_pytest`, medi012 head)
- 마이그레이션 계보: … → medi010 → medi011 → medi012_questionnaire_engine

## 재분석 결과

ARCH-DB-4a39d6a5 는 after 보고서에서 제거됨. CLOSED는 재분석 증거에 근거한다.

## 미해결 위험

- 전자서명·외부 봉인 미구현
- OSDI rounding UNSPECIFIED
- 브라우저 E2E 미검증
- Analyzer 추천 4건 미수정
- LLM 로컬 엔드포인트 비가용
