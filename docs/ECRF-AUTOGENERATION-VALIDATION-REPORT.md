# eCRF 초안 검증

## 2026-10-27T08:52:53+09:00 — PC2-EYECARE-PHASE012-COMPLETION-AND-DOCKER-VALIDATION-002

호스트는 SVG-SKLEE다. 브랜치는 `feat/protocol-ecrf-autogen-audit-012`, HEAD는 `a81b410`이다. WSL2는 `6.18.54.1-microsoft-standard-WSL2`, Docker Engine은 29.9.1, Compose는 v5.6.0이다. GPU는 NVIDIA GeForce RTX 2080이며 이번 검증은 GPU를 쓰지 않았다.

포트 레지스트리 파일은 `\\MEDIIOT-SKLEE\idea-collection\projects\PORT-ALLOCATION.md`이고 SHA-256은 `5d97108c4bb335cfd3653ec32d9b7c91302b34f6947f38bee0f4c9f822fed734`다. MEDI-IOT API 호스트 포트는 8001이다. 그 포트의 기존 uvicorn(PID 14244)은 유지했다. 8772의 격리 시연(PID 12472)과 55444의 기존 Postgres는 레지스트리 배정이 아니라 이전 작업의 리스너라 종료하지 않았고, 이번 검증의 근거로 쓰지 않았다. 1234는 등록된 LM Studio 포트이며 응답이 없었다.

Docker 네트워크 `ecrf012-net`에 PostgreSQL 15(`pgvector/pgvector:pg15`)와 Redis를 호스트 포트 없이 띄웠다. `alembic upgrade head`는 종료 코드 0이고 개정은 `medi011_protocol_ecrf_audit`이다. 체인 UPDATE는 `append-only clinical history`로 거부됐다. 컨테이너 안에서 `/health`는 200, `/protocol-ecrf`는 200, 토큰 없는 스키마 조회는 401, doctor와 manager 토큰의 비구성원 조회는 403이다. 컨테이너 `ecrf012-pg`, `ecrf012-redis`, `ecrf012-py`, `ecrf012-app`과 이미지 `ecrf012-deps`는 검증 후 삭제했다.

Windows pytest는 71 passed, 4 skipped, 종료 코드 0이다. 대상은 계획서 eCRF, 대시보드, 가져오기, 잠금, 질의, 모델, 임상 API, 관찰 수명주기이다. Docker pytest는 PostgreSQL 3건과 eCRF 6건이 9 passed, 종료 코드 0이다.

요구와 테스트의 대응:

| 요구 | 테스트 |
| --- | --- |
| 버전별 초안과 OSDI 방문 차이 | `test_versions_stay_distinct_and_audit_is_append_only` |
| 잠금과 반복 범위 | `test_locked_visit_and_bad_repeat_do_not_write` |
| 개정 충돌 | `test_duplicate_revision_is_rejected` |
| 삭제된 필드와 무기록 롤백 | `test_removed_field_and_rollback_keep_original_value` |
| 감사 실패 시 입력 취소 | `test_audit_failure_does_not_keep_the_entry` |
| 해당 없음 문항 | `test_not_applicable_osdi_item_is_accepted` |
| PostgreSQL 개정 medi011 | Docker의 import, query, lock PostgreSQL 테스트 |

## 이전 기록

실행 호스트는 SVG-SKLEE다. 브랜치는 `feat/protocol-ecrf-autogen-audit-012`이고 기준은 `a81b410`이다. 커밋과 푸시는 하지 않았다.

## 원본

로컬 PDF 세 개의 SHA-256을 다시 계산했다. 본문은 출력하지 않았다.

| 파일 | 바이트 | SHA-256 |
| --- | ---: | --- |
| Protocol v1.3 | 3403929 | `39c51490afb38c8b44aebbaaa4a5bb9186e29d29292fb1726138462272fbff91` |
| v1.3 변경표 | 427880 | `9d1baddb2bb1be6e5f36ccf64e3871ebfcc73566f87a9dc2570eddc80b82ff39` |
| Protocol v1.10 | 3582719 | `9e24fcedbd869e4e2b88d8b33e32acf617d4fd541199c78cd4c75d6444e2ac44` |

초안 생성은 이 파일의 문장을 다시 해석하지 않는다. `services/clinical_protocol_rules.py`에 이미 있는 방문 표와 규칙 묶음을 `reviewed_rule_pack`으로 읽는다. 신뢰도는 `source_metadata`이고 `proposal`은 참이다.

## 합성 시나리오

`tests/test_protocol_ecrf.py`가 메모리 SQLite에서 다음을 확인했다.

1. 1.3과 1.10을 각각 등록하고 초안을 만든다.
2. 승인은 `SIMULATED_APPROVAL`이다.
3. 1.3 스키마의 V5 `OSDI-SCORE`와 1.10 스키마의 V1 `TBUT-OD-REPEAT`를 따로 저장한다.
4. OSDI만 `CHANGED_VISIT_SCHEDULE`이다. TBUT 논리 필드는 `UNCHANGED`다.
5. 건식 매핑의 쓰기 수는 0이다.
6. 잠긴 방문과 범위 밖 반복 번호는 행을 늘리지 않는다.
7. 같은 개정 번호는 무결성 제약으로 거부한다.
8. 감사 체인 UPDATE는 거부한다.

측정값은 이 문서에 적지 않는다.

pytest 종료 코드는 0이다. `test_protocol_ecrf.py`, `test_clinical_case_dashboard.py`, `test_clinical_import.py`, `test_clinical_data_lock.py`, `test_clinical_query_quality.py`, `test_clinical_support_models.py`, `test_clinical_api.py`는 63 passed, 3 skipped다. 건너뛴 3건은 기존 PostgreSQL 전용 테스트다.

일회용 PostgreSQL 15에서 `alembic upgrade head` 종료 코드는 0이고 개정은 `medi011_protocol_ecrf_audit`다. 체인 행 UPDATE는 `append-only clinical history`로 실패했다. 컨테이너는 삭제했다.

브라우저 `http://127.0.0.1:8772/protocol-ecrf`에서 1.10 초안 7개 필드가 보였고, 다른 사이트 값 뒤에는 필드와 이력이 비워졌다. 이 화면은 합성 SQLite 시연이며 전체 앱의 JWT 경로는 아니다.

## LLM

`http://127.0.0.1:1234/v1/models`는 연결되지 않았다. 로컬 LM Studio를 그 주소에서 켠 뒤에야 방문 추출 제안을 추가할 수 있다. 그 전까지 모델 출력을 승인된 규칙으로 저장하지 않는다.

## 남은 공백

정식 서명, 방문 ±3일과 ±7일, Visit 4 처치, OSDI 반올림은 해결하지 않았다. 규칙 묶음은 ACTIVE가 아니고 R1과 창 검사는 꺼져 있다.
