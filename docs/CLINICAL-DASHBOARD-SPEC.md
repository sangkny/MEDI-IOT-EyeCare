# 증례 대시보드 명세

화면은 앱 루트의 `/clinical-dashboard`다. 임상 데이터는 `/api/v1/clinical-support` 아래에 둔다.

## 진행 기록

### 2026-10-27T00:16:54+09:00 — 게시

- TASK_ID: PC2-EYECARE-DASHBOARD-010-PUBLICATION-005
- EXECUTION_HOST: SVG-SKLEE (PC2)
- BRANCH: feat/clinical-case-dashboard-010
- BASE_HEAD: 600ac7bd6f3dca5b7ef8cc998c621b43828a5f16
- CODE_COMMIT: bf95fc5a327653a710adbd328e3b12a52cd6a784
- START_TIME_KST: 2026-10-27T00:16:54+09:00
- END_TIME_KST: 2026-10-27T00:19:49+09:00
- ELAPSED: PT2M55S
- STATUS: DASHBOARD010_PUBLISHED
- 의존성: `requirements.txt`의 `pydantic==2.10.3`을 유지했다. `shared-libs-requirements.txt`의 `google-genai` 상한을 `<2.9.0`으로 두어 해석 결과가 `google-genai` 2.8.0, `anthropic` 2.3.0, `pydantic` 2.10.3이 되게 했다. 이 조합으로 `import main`이 성공했다
- 런타임: 기존 프로세스 `127.0.0.1:8001`의 `/health` 200, `/clinical-dashboard` HTML 200. 합성 `SYN-01`의 V1·V2, FINAL과 DRAFT 분리, `enable_r1` false를 다시 조회했다. 새 브라우저 탭에서도 화면이 열렸다
- 테스트: 대시보드·가져오기·API·모델·정책 41 passed, 1 skipped, exit 0. 잠금·질의 27 passed, 2 skipped, exit 0. 이번 게시에서 PostgreSQL은 다시 실행하지 않았다
- 리스너: 8001, 8766, 8767과 일회용 PostgreSQL 컨테이너는 화면 세션을 유지하기 위해 종료하지 않았다. 포트 할당 문서는 수정하지 않았다
- 커밋은 코드와 문서를 나눴다. PR은 만들지 않았다

### 2026-10-26T20:40:41+09:00 — 전체 앱 기동

- TASK_ID: PC2-EYECARE-DASHBOARD-010-FULL-RUNTIME-FIX-004
- EXECUTION_HOST: SVG-SKLEE (PC2)
- BRANCH: feat/clinical-case-dashboard-010
- HEAD: 600ac7bd6f3dca5b7ef8cc998c621b43828a5f16
- START_TIME_KST: 2026-10-26T20:40:41+09:00
- END_TIME_KST: 2026-10-26T20:50:46+09:00
- ELAPSED: PT10M5S
- STATUS: FULL_EYECARE_DASHBOARD_VERIFIED
- 원인: shared-libraries `llm/__init__.py`가 공급자를 즉시 임포트한다. `shared-libs-requirements.txt`는 `anthropic>=0.28.0`, `google-genai>=1.0.0`을 실행 의존성으로 적는다. `setup.py` extras는 선택 설치로도 적혀 있다. 격리 venv에는 두 패키지가 없었다
- 조치: 격리 venv `C:\Tools\venvs\eyecare-phase004`에 `anthropic` 2.3.0, `google-genai` 2.33.0을 설치했다. 해석기가 `pydantic`을 핀 2.10.3에서 2.14.1로 올렸다. 저장소 requirements 파일은 바꾸지 않았다
- 전체 앱: `127.0.0.1:8001`. `GET /health` 200, `db_connected` true. `GET /clinical-dashboard` 200 HTML. 데이터 API는 JSON. 인증 401, manager와 비구성원 403
- 포트: `PORT-ALLOCATION.md`의 medi-iot-api 호스트 포트는 8001이다. 8000은 테스트가 요구하는 주소라 테스트 동안만 사용하고 종료했다. 문서는 수정하지 않았다
- 브라우저: `http://127.0.0.1:8001/clinical-dashboard`에서 합성 `SYN-01`, V1/V2, FINAL/DRAFT, 결측, 질의 open 1, 배치 1을 확인했다
- 테스트: `tests/test_clinical.py` 15 passed, exit 0. 대시보드·가져오기·잠금·질의·API·모델·정책 68 passed, 3 skipped, exit 0. 빈 PostgreSQL에서 잠금 1 passed, 가져오기 1 passed, exit 0. 질의 PostgreSQL 1 passed
- 남은 프로세스: 전체 앱 PID 14244 포트 8001, 일회용 PostgreSQL `eyecare-dashboard-010-app-pg` `127.0.0.1:55444`, 격리 대시보드 포트 8767. 8766은 PID 3276이 점유 중이며 이 세션에서 종료가 거부되었다
- 커밋과 푸시 없음

### 2026-10-26T19:35:01+09:00 — 런타임 검증

- TASK_ID: PC2-EYECARE-DASHBOARD-010-RUNTIME-VALIDATION-002
- EXECUTION_HOST: SVG-SKLEE (PC2)
- BRANCH: feat/clinical-case-dashboard-010
- HEAD: 600ac7bd6f3dca5b7ef8cc998c621b43828a5f16
- START_TIME_KST: 2026-10-26T19:35:01+09:00
- END_TIME_KST: 2026-10-26T19:48:09+09:00
- ELAPSED: PT13M8S
- STATUS: PARTIALLY_VERIFIED

#### 전체 앱 기동

`PYTHONPATH`에 작업 트리와 shared-libraries를 두고 `import main`을 실행했다. 프로세스는 대기하지 않고 임포트 단계에서 끝났다.

실패 위치는 `main.py`가 `api` 패키지를 불러온 뒤, 기존 `api/dashboard.py` → `services/dashboard_service.py` → `services/llm_telemetry.py` → `llm/__init__.py` → `anthropic_provider.py`의 `import anthropic`이다. 예외는 `ModuleNotFoundError: No module named 'anthropic'`.

`anthropic`만 임시 모듈로 바꾸면 다음 실패는 `google.genai`다. 둘 다 기존 LLM 공급자 임포트이고 증례 대시보드 코드가 아니다. 수명주기, 데이터베이스, Redis, 인증 미들웨어까지 도달하지 못했다. 인증을 끄거나 운영 대시보드 임포트를 지우지 않았다.

그래서 `uvicorn main:app`의 화면 주소는 이번 실행에서 확인하지 못했다. `main.py`는 기동이 성공할 때 `/clinical-dashboard`를 등록한다.

#### 확인한 주소

격리 명령:

`C:\Tools\venvs\eyecare-phase004\Scripts\python.exe C:\Office_Automation\MEDI-IOT-EyeCare-dashboard-010\scripts\run_case_dashboard_isolated.py`

확인한 화면: `http://127.0.0.1:8766/clinical-dashboard`

- 화면 응답: 200, `text/html; charset=utf-8`
- 데이터 응답: 200, `application/json`
- CSS와 JS는 HTML 안에 있다. 외부 자산 URL은 없다
- 검증 후 포트 8766 프로세스와 `data/synthetic-case-dashboard.sqlite`를 지웠다

이 venv에는 저장소가 핀한 `uvicorn==0.32.1`이 없어 검증 중에 그 패키지를 설치했다. 저장소 파일은 바꾸지 않았다.

#### 브라우저

합성 행만 있는 격리 서버에서 브라우저로 다음을 수행했다.

1. 토큰, 연구 ID, 사이트 ID 입력
2. 사이트 집계 표시
3. `SYN-01` 선택
4. V1 `2026-03-02`, V2 `2026-03-03` 타임라인
5. FINAL TBUT OD `reported_average`와 DRAFT TBUT OD `repeat`를 분리 표시
6. TBUT, OSDI_SCORE, SCHIRMER의 결측 분모
7. 출처 표에 방문, 눈, 방법, 상태, `import`, 단위
8. 품질·질의 건수와 가져오기 배치 0

화면 주소는 `/clinical-dashboard`에 머물렀다. 대상자 코드는 데이터 요청의 `subject_code`로만 전달된다.

이 브라우저 시드에는 V5·V6, 비숫자 값, 질의 행이 없다. 그 경우는 테스트가 담당한다. 전체 앱 브라우저 흐름은 기동 실패 때문에 실행하지 못했다.

#### 보안

서버 테스트에서 확인한 응답:

- 토큰 없음: 401
- `clinical_observation_read`가 없는 manager: 403
- 사이트 비구성원: 403
- 다른 연구 ID: 400
- 다른 사이트의 대상자 코드: 400, 응답에 그 코드 없음
- `subject_code` 65자, 연구 ID 40자: 422
- 배정 문자 `ARM-X`는 응답에 없음
- 비구성원의 출처 조회: 403

대상자를 지정하지 않으면 `subject_series`는 null이다. 집계는 코드별 건수와 확정·초안 상자만 내려 준다.

#### 테스트

- `tests/test_clinical_case_dashboard.py`: 4 passed, exit 0
- 같은 파일과 shared-libraries `tests/test_policy.py`: 12 passed, exit 0. 정책 테스트 8개 포함
- `tests/test_clinical_import.py`, `test_clinical_data_lock.py`, `test_clinical_query_quality.py`, `test_clinical_api.py`, `test_clinical_support_models.py`, `test_clinical.py`, 정책 테스트를 한 프로세스에서 실행: 64 passed, 15 failed, 3 skipped, exit 1
- 실패 15건은 `tests/test_clinical.py`가 `localhost:8000`에 접속하다 연결이 거절된 것이다. 대시보드 단정 실패가 아니다
- 건너뛴 3건은 PostgreSQL URL이 없던 기존 통합 테스트다
- 이어서 일회용 PostgreSQL 15 `127.0.0.1:55443`, `CREATE EXTENSION vector`, Alembic `medi010_external_clinical_import`, `test_postgresql_import_migration_when_configured` 1 passed, exit 0
- 컨테이너 `eyecare-dashboard-010-pg`는 중지 후 제거했다

#### 남은 제한

전체 EYECARE 프로세스는 기존 LLM 공급자 패키지가 없어 시작하지 못한다. 질의 상세 화면과 감사 이벤트 원문은 대시보드에 없다. 출처 표는 선택 대상자의 관찰 메타데이터만 보여 준다. v1.10 규칙 활성화, R1, 방문 창 강제, 값 수정, 확정, 잠금은 하지 않는다.

#### 수정 파일

- `api/__init__.py`
- `api/clinical_dashboard.py`
- `main.py`
- `services/clinical_case_dashboard.py`
- `static/clinical-dashboard/index.html`
- `tests/test_clinical_case_dashboard.py`
- `scripts/run_case_dashboard_isolated.py`
- `docs/CLINICAL-CASE-DASHBOARD-010.md`
- `docs/CLINICAL-MODULE-IMPLEMENTATION-ROADMAP.md`
- `docs/CLINICAL-DASHBOARD-SPEC.md`
- `docs/CLINICAL-VISUAL-ANALYTICS-SPEC.md`
