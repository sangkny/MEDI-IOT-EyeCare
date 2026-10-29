# 계획서 개정과 버전 보존

비교는 두 스키마의 논리 필드 합집합이다. 한쪽에만 있으면 `ADDED` 또는 `REMOVED`다. 방문 목록이 다르면 `CHANGED_VISIT_SCHEDULE`이다. 문항이 없는 양식은 `ambiguous_forms`에 남는다. `rollback_plan`과 `dry_run_mapping`의 쓰기 수는 0이다. 같은 비교를 반복해도 기존 입력 값은 그대로다.

# 이전 명세

## 버전 식별

지원 라벨은 `1.3`과 `1.10`이다. 논리 필드 ID는 두 버전에서 같다.

- `TBUT-OD-REPEAT`, `TBUT-OD-AVG`, `TBUT-OS-REPEAT`, `TBUT-OS-AVG`
- `SCHIRMER-OD`, `SCHIRMER-OS`
- `OSDI-SCORE`

단위는 초, `mm/5min`, score다. 창 검사는 두 버전 모두 거짓이다.

OSDI 방문만 출처가 다르다. 1.3 부록 칸은 V1–V5다. 1.10 부록 칸은 V1, V2, V3, V4, V6이다. TBUT와 Schirmer의 1.3 방문 칸은 이번 추출에서 새로 확정하지 않았으므로 1.10 일정 격자와 같은 방문으로 두고 `UNCHANGED`다.

## 개정 분류

비교는 스키마 본문만 본다. 분류는 `ADDED`, `REMOVED`, `CHANGED_VISIT_SCHEDULE`, `CHANGED_UNIT`, `UNCHANGED`다. 이름 변경, 분할, 병합은 이번 두 버전의 논리 ID에서 나오지 않았다.

미결은 스키마에 그대로 남는다.

- `FORMAL_SIGNATURE`
- `WINDOW_3_VS_7`
- `VISIT4_TREATMENT`
- `OSDI_ROUNDING`

## 보존

새 스키마는 새 ID다. 이전 입력의 수치를 고치지 않는다. `dry_run_mapping`은 쓰기 수가 0이고, 각 필드를 `preserve`로만 제안한다. 활성화된 이전 스키마도 계속 렌더링할 수 있다.
