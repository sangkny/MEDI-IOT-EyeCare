# 13 다중 프로토콜 MEDI-AMD-001 검증

실행 호스트는 PC1 `MEDIIOT-SKLEE`다. 2026-10-29 격리 통합에서 확인한 내용만 적는다.

## 문제

DES와 AMD 초안이 같은 플랫폼에 들어가면 폼 카탈로그와 승인되지 않은 규칙이 섞일 수 있다.

## 구현 결정

MEDI-AMD-001은 별도 연구 ID와 폼 카탈로그로 둔다. OSDI는 DES에만 두고, AMD는 BCVA·OCT·Study Eye를 제안한다. AMD-WAVE, AMD-SCHED-V6, AMD-DATA-RETENTION, AMD-DESIGN-RAND는 CONFIRMED_CONFLICT로 남기고 `rules_active`는 false다. 마이그레이션 헤드는 `medi012`를 유지한다.

## 실험과 결과

컨테이너에서 SQLite 100 passed, 4 skipped, 정책 8 passed, PostgreSQL 양방향 각 4 passed였다. SVG-Analyzer 어댑터 `55f7105`로 `eyecare-architecture-evidence/1` 오프라인 리뷰를 돌렸고 발견 4건은 모두 UNASSESSED이며 임상 규칙은 바꾸지 않았다.

## 아직 없는 것

AMD 초안을 운영 승인으로 승격하지 않는다. 호스트 브라우저 JWT E2E는 수행하지 않았다.

## 다시 쓸 수 있는 설명

충돌 발견은 기록만 하고, 자동 보정이나 자동 잠금으로 넘기지 않는다.
