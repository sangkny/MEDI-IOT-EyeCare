# MEDI-AMD-001 다중 프로토콜 검증 + Phase 012 통합 재검토

갱신: 2026-10-29T17:28:46+09:00 KST  
작업: PC2-EYECARE-AMD013-SAFE-PUBLICATION-004  
호스트: SVG-SKLEE (PC2)  
게시 기반: Phase 012 `9ab5b0df385a8ddd4e8974f1090cd19075b7bb94`  
문서 상태: MEDI-AMD-001 **DRAFT** (승인·운영 활성 아님)

## Git / 환경

| 항목 | 값 |
| --- | --- |
| ecrf-012 | `feat/protocol-ecrf-autogen-audit-012` @ a81b410 + 미커밋 Phase 012 |
| amd-013 | `feat/multi-protocol-amd-validation-013-prep` @ a81b410 + 미커밋 Phase 013 |
| SVG-Analyzer | `feat/eyecare-architecture-review-adapter-001` @ `55f710569e89f0fee5b86a71da41230a1fcd661f` |
| Port Registry | `\\MEDIIOT-SKLEE\idea-collection\projects\PORT-ALLOCATION.md` |
| Port SHA-256 | `5D97108C4BB335CFD3653EC32D9B7C91302B34F6947F38BEE0F4C9F822FED734` |
| Listeners kept | 8001, 55444 (8772 당시 미청취 가능) |

원본 Protocol은 Git 밖 `data/` 에만 둠. `local_analysis/` gitignore.

## 1. Phase 012/013 의존 매트릭스

`PHASE012-013-DEPENDENCY-MATRIX.md` 참조.  
**013은 미커밋 012 Protocol/eCRF/Audit/Evidence에 의존.** 디렉터리 통째 복사 없음.

## 2. 교정된 Protocol findings

Source SHA-256 `85B946928FFCC33FAF1C858D8BC745186BAE3298B737B8B11AED9A3EC54330F5` (일치). 상태 **DRAFT**.

| ID | 이전 | 교정 | 근거 요지 |
| --- | --- | --- | --- |
| AMD-WAVE | SOURCE_VERIFIED (3파장만) | **CONFIRMED_CONFLICT** | 3파장 기기 서술 + 치료설정 590/680/780/830 nm·조사강도. 문단~87, 기기표~12 |
| AMD-SCHED-V6 | CONFIRMED | CONFIRMED | 일정 방문1–5 vs 본문 방문6(21주) |
| AMD-EP-VISIT | POSSIBLE | POSSIBLE | 1차 BCVA 5·9주, 방문6/21주 이차·절차 |
| AMD-N15-N16 | CONFIRMED | **POSSIBLE** | 산출 16과 파일럿 등록 15 공존. 동일 필수요건으로 단정 금지 |
| AMD-DATA-RETENTION | CONFIRMED | CONFIRMED | 철회 파기 vs 탈락 보관. **정책 변경 미실시** |
| AMD-DESIGN-RAND | CONFIRMED | CONFIRMED | Single-Arm vs 무작위배정 용어 |
| AMD-TX-SETTINGS | POSSIBLE | POSSIBLE | 파장/출력/모드/노출/빈도 분리 검토 |

설문: OSDI 미기재. DES OSDI 발명·이식 금지.

## 3. 다중 연구 모듈 재사용

| 공유 엔진 | DES | AMD |
| --- | --- | --- |
| Protocol Registry / eCRF Schema | OSDI·TBUT·Schirmer catalog | BCVA·OCT·Study Eye catalog |
| Questionnaire Engine | 사용 | **미연결** |
| Audit / Auth / Dashboard / Stats interface | 공유 | 공유 |
| 질병 하드코딩 in generic services | 없음 (catalog 분리) | 없음 |

## 4. Analyzer 호환

계약 식별자: `eyecare-architecture-evidence/1` (ADAPTER_SCHEMA).  
오프라인 리뷰: recommendation 위주 (IFACE/LOSS/MIG). confirmed disease-coupling defect 없음.  
환자·Protocol 본문 Analyzer 미제공.

## 5. 회귀

별도 섹션/실행 로그에 기록 (Docker PG15 → medi012, synthetic).

## 6. 최소 통합 계획

1. 012 게시 (migrations + protocol/questionnaire/audit/evidence)
2. 013에서 AMD catalog/findings/tests만 추가 PR
3. `register_form_catalog("MEDI-AMD-001")` 호출 지점만 연결
4. unresolved findings를 ACTIVE 규칙으로 승격하지 않음
5. 데이터 보존/삭제 정책 코드화 금지(검토 전)

## 7. Git 게시 순서

1. Phase 012  
2. Phase 013 AMD  
3. Analyzer closure(선택)  

커밋/푸시 이번 작업에서 수행하지 않음.
