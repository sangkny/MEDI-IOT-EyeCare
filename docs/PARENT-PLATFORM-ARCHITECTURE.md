# 부모 플랫폼 구조

> 작업: EYECARE-CLINICAL-SUPPORT-005. 읽기 전용 클론과 일회용 데이터베이스만 사용했다.  
> PC1의 `idea_collection/projects` 원본은 수정하지 않았다.  
> 비밀 값, 개발 계정, 컴포즈 기본 자격 증명은 적지 않는다.

## 진행 기록

### 2026-10-23 09:15 KST — Phase 007과 문서 커밋 분리

- TASK_ID: PC2-CLINICAL-PHASE007-CHECKPOINT-001
- EXECUTION_HOST: SVG-SKLEE
- PC_ROLE: PC2
- REPOSITORY: MEDI-IOT-EyeCare
- LOCAL_PATH: C:\Office_Automation\MEDI-IOT-EyeCare
- BRANCH: feat/clinical-query-quality-007
- HEAD_BEFORE: a8661d5ab665f686b2e81ef9c0be1e8f633c8e93
- HEAD_AFTER: 기능 커밋 `1647b83b557abbc85d9778cfbf816d8aab3cf518`. 이 문서는 그 다음 커밋
- START_TIME_KST: 2026-10-23T09:14:23+09:00
- END_TIME_KST: 2026-10-23T09:16:56+09:00
- FILES_CHANGED: 이 문서만
- TEST_RESULTS: 기능 커밋 전 SQLite 26 passed, 2 skipped. PostgreSQL 15 `medi008_clinical_query` 2 passed. shared-libraries 정책 7 passed, 커밋 `a9d2dbd13df94d4be284c96c801f00dcff4f7956`
- REMAINING_ISSUES: 부모 2026-10-23 문서는 GitHub `main`에 없음. Phase 008은 시작하지 않음

### 2026-10-23 08:56 KST — PC2 문서 기준 정렬

- TASK_ID: PC2-PLATFORM-DOCUMENTATION-SYNC-001
- EXECUTION_HOST: SVG-SKLEE
- PC_ROLE: PC2
- REPOSITORY: MEDI-IOT-EyeCare
- LOCAL_PATH: C:\Office_Automation\MEDI-IOT-EyeCare
- BRANCH: feat/clinical-query-quality-007
- HEAD_BEFORE: a8661d5ab665f686b2e81ef9c0be1e8f633c8e93
- HEAD_AFTER: a8661d5ab665f686b2e81ef9c0be1e8f633c8e93
- START_TIME_KST: 2026-10-23T08:56:40+09:00
- END_TIME_KST: 2026-10-23T09:00:20+09:00
- FILES_CHANGED: 이 문서만. Phase 007에서 이미 수정된 임상 문서와 코드는 다시 고치지 않음
- TEST_RESULTS: 애플리케이션 테스트를 다시 실행하지 않음. 포트는 읽기만 함
- REMAINING_ISSUES: 부모 `docs/PLATFORM-ARCHITECTURE.md`, `docs/CROSS-PROJECT-INTEGRATION.md`, `PORT-ALLOCATION.md`의 2026-10-23 절은 PC1 작업 트리에만 있다. GitHub `main`에는 없다. `PENDING_PC1_PUBLICATION`

### 2026-10-22 22:42 KST — PC2 기능 브랜치 게시

- 작업 ID: PC2-CLINICAL-GIT-PUBLISH-001
- 시작: 2026-10-22T22:42:55+09:00
- 종료: 2026-10-22T22:45:21+09:00
- PC: SVG-SKLEE / PC2
- 저장소: MEDI-IOT-EyeCare `feat/clinical-support-002` 커밋 `3d8e5702e439db7cfd658e42b6977520845260a2`. shared-libraries `feat/medi-iot-clinical-policy` 커밋 `81a222baaa3ee256fe13fb33494ab2b6fd73ec76`
- push: 두 기능 브랜치만 origin에 새로 생성. PC1 공유와 부모 submodule 포인터는 변경하지 않음
- 테스트: 게시 전 합성 19 passed, 정책 6 passed
- 남은 문제: 부모 `projects`는 이 브랜치들을 아직 가리키지 않음
- 다음 승인: 브랜치 검토와 main 병합

### 2026-10-22 22:13 KST — Phase 006 PC1 확인과 임상 API

- 작업 ID: EYECARE-CLINICAL-SUPPORT-006
- 시작: 2026-10-22T22:13:52+09:00
- 종료: 2026-10-22T22:26:48+09:00
- PC: SVG-SKLEE
- 저장소: MEDI-IOT-EyeCare `feat/clinical-support-002`, HEAD `a5e2f71f98011ad52684bef62ded28432a5f8df0` (커밋 전). shared-libraries 로컬 클론 `bd7d353`의 `auth/policy.py`만 수정. PC1은 읽기만 함
- 변경: PC1 공유 `\\MEDIIOT-SKLEE\idea-collection` 확인. 임상 HTTP와 eCRF 기초, medi007 초안
- 테스트: 합성 SQLite 19 passed, PostgreSQL URL 없는 1 skipped. 일회용 PostgreSQL 15.19에서 `medi007_ecrf_foundation`까지 업그레이드. API 저장, 동시 정정, rollback 확인 후 컨테이너 삭제
- 남은 문제: 부모 핀 `5bc2147`은 정책 파일만 대조했고 런타임으로 실행하지 않음. MEDI-DES-001 문항은 BLOCKED_PENDING_SOURCE
- 다음 승인: 저장소별 커밋. Phase 007은 시작하지 않음

### 2026-10-22 21:45 KST — Phase 005 부모 구조와 관찰 수명주기

- 작업 ID: EYECARE-CLINICAL-SUPPORT-005
- 시작: 2026-10-22T21:45:27+09:00
- 종료: 2026-10-22T21:55:58+09:00
- PC: SVG-SKLEE
- 저장소: MEDI-IOT-EyeCare, 브랜치 `feat/clinical-support-002`
- HEAD: `a5e2f71f98011ad52684bef62ded28432a5f8df0` (커밋 전)
- 변경: 부모 구조 문서, 관찰 초안·확정·정정 서비스, 미적용이던 `medi006`에 사유·확정 열 추가, 합성 테스트
- 테스트: 합성 SQLite 15 passed, PostgreSQL 전용 1 skipped. 일회용 PostgreSQL에서 `alembic upgrade head`가 `medi006_clinical_support`에 도달. 같은 데이터베이스에서 수명주기 테스트 1 passed, 동시 정정은 개정 2 하나와 `ClinicalRecordError` 하나. 컨테이너는 삭제
- 남은 문제: PC1 로컬 계층은 UNKNOWN. shared-libraries 핀 `5bc2147`은 shallow 클론에서 재현하지 못했다. 임상 HTTP는 노출하지 않음
- 다음 승인: 커밋. shared-libraries 정책에 임상 액션을 넣는 별도 저장소 변경. Phase 006 착수

## 1. 확인된 위상

읽기 전용 클론은 `C:\Tools\downloads\phase005-inspect`에 있다. EYECARE 작업 트리 밖이다.

| 저장소 | 확인한 HEAD 또는 gitlink | 역할 |
|--------|--------------------------|------|
| projects `main` | `283ffc0e2b714ba9080e1719051816a44e1a9087` | 부모 오케스트레이션 |
| projects가 가리키는 MEDI-IOT-EyeCare | `1c8bd4a7f86d3501958d3a62dcee4f8516d146a7` | 임상 애플리케이션 서브모듈 |
| 로컬 MEDI-IOT-EyeCare | `a5e2f71f98011ad52684bef62ded28432a5f8df0` | 이 개발 호스트의 임상 작업 기준 |
| projects가 가리키는 shared-libraries | `5bc2147cfb4151ab693efa3c8a80183c20fde5f9` | 부모 컴포즈가 기대하는 라이브러리 핀 |
| 이번 검증에 쓴 shared-libraries `main` | `bd7d353f90328b8fecb31df897a8e74ecd5e0c43` | CI와 같이 depth 1로 받은 기본 브랜치 |
| AutoNoGaDa-ADK gitlink | `e180dd884f0f71b82e6ad05c25ae3d6293b2ae3e` | 부모 서브모듈. 이번 단계에서 수정하지 않음 |
| CoOps-Platform gitlink | `52150ea8120c7cbbe1bde4121842da9aa437eb56` | 부모 서브모듈. 이번 단계에서 수정하지 않음 |

로컬 EYECARE HEAD와 부모 gitlink는 다르다. 서브모듈 포인터는 옮기지 않았다.

관계는 다음과 같다.

`idea_collection/projects`는 PC1에서 부모 저장소를 두는 자리로 지시되었다. SVG-SKLEE의 `C:\idea_collection`, `C:\Office_Automation\idea_collection`, `D:\idea_collection`에는 그 트리가 없다. PC1 전용 구조는 UNKNOWN이다.

GitHub의 `projects`는 부모다. `.gitmodules`는 `shared-libraries`, `MEDI-IOT-EyeCare`, `AutoNoGaDa-ADK`, `CoOps-Platform`을 `https://github.com/sangkny/` 아래 서브모듈로 둔다. 부모는 배포 구성과 문서, 대시보드, 헬스 집계, 관찰 스택을 함께 둔다. 임상 모델과 마이그레이션의 소유 저장소는 MEDI-IOT-EyeCare다. 인증·정책·과금 모델 팩토리의 소유 저장소는 shared-libraries다.

## 2. 의존성 적재

EYECARE `requirements.txt`는 shared-libraries를 pip 의존성으로 핀하지 않는다. 부모 `docker-compose.dev.yml`의 `medi-iot-api`는 `./shared-libraries`를 `/app/shared-libraries`에 마운트하고 `PYTHONPATH=/app/shared-libraries:/app`를 쓴다. 기동 명령은 `alembic upgrade head` 뒤에 CNN 동기화와 uvicorn이다. 이 컴포즈는 시작하지 않았다. 개발용 데이터베이스와 객체 저장소 기본값이 파일에 있으며, 그 값은 여기 옮기지 않는다.

EYECARE CI는 shared-libraries `main`을 depth 1로 클론한다. 버전 핀은 없다. 이번 격리 검증은 그 CI 방식을 따랐다. 부모 gitlink `5bc2147`은 shallow 클론에 객체가 없어 실행하지 못했다. 핀과 `main`의 동작 차이는 UNKNOWN이다.

`models/__init__.py`는 billing을 먼저 불러오고, billing은 `saas`를 불러온다. `alembic/env.py`의 `import models.medical`도 같은 경로를 탄다. 가짜 모듈은 만들지 않았다. 격리 venv `C:\Tools\venvs\eyecare-phase004`에 shared-libraries `setup.py`가 선언한 패키지와 EYECARE가 핀한 `fastapi==0.115.6`, `python-multipart==0.0.12`를 설치한 뒤, `PYTHONPATH`를 클론으로 두고 `import models.medical`과 `import models.knowledge`가 성공했다.

## 3. 인증과 서비스 경계

shared-libraries `auth`의 `current_user_strict`는 Bearer 액세스 토큰을 요구한다. `medi-iot` 정책의 doctor 액션은 `read`, `create_exam`, `ai_analyze`, `upload_image`, `promote_diagnosis`, `review_diagnosis`다. staff는 `read`, `create_patient`다. admin은 `*`다. 임상 관찰의 초안·확정·정정 액션은 없다.

연구·사이트 구성원 검사는 EYECARE `StudySiteMember`다. shared-libraries에는 없다. 정책 액션을 넣으려면 shared-libraries 변경이 필요하고, 그 저장소 커밋은 이 단계 승인이 아니다. 그래서 임상 HTTP 라우트는 추가하지 않았다. 서비스 계층의 초안·수정·확정·정정은 사이트 구성원을 검사한다.

부모 대시보드와 health-aggregator는 의료 API 상태를 소비하는 입구다. 임상 지원 라우트를 그 입구에 연결하지 않았다.

## 4. 환경 차이

| 항목 | 부모 컴포즈에서 확인 | 이번 SVG-SKLEE 검증 |
|------|----------------------|---------------------|
| Postgres 이미지 | `pgvector/pgvector:pg15` | 일회용 `pgvector/pgvector:pg16`, `127.0.0.1:55433`, 종료 후 삭제 |
| vector 확장 | 앱 `database.py`가 기동 시 생성. `c45` 마이그레이션은 생성하지 않음 | 업그레이드 전에 일회용 DB에서만 `CREATE EXTENSION` |
| shared-libraries | 볼륨 마운트와 부모 gitlink | CI와 같은 `main` `bd7d353` |
| PC1 | 지시서의 원본 위치 | 이 호스트에서 UNKNOWN |

운영 데이터베이스, PC1 볼륨, DeeVo에는 접속하지 않았다. downgrade는 실행하지 않았다.

## 5. 가정과 확인의 구분

확인: 부모 HEAD, 네 개의 gitlink, 컴포즈의 마운트와 `PYTHONPATH`, CI의 depth 1 클론, 정책 액션 목록, `saas` 포함 임포트, 일회용 PostgreSQL에서 `medi006`까지의 업그레이드.

UNKNOWN: PC1 디렉터리의 추가 설정, shared-libraries 핀 `5bc2147`과 `bd7d353`의 차이, 컴포즈를 실제로 기동했을 때의 호스트 LM Studio·MQTT 연결.

가정으로 코드를 맞추지 않은 것: 부모와 로컬 EYECARE가 같은 HEAD라는 전제, shared-libraries를 EYECARE 안에 복제하는 방법, 정책에 임상 액션이 이미 있다는 전제.

## 6. Phase 006에서 확인한 PC1

SVG-SKLEE에서 `\\MEDIIOT-SKLEE\idea-collection`를 읽기만 했다. 파일 생성·수정·삭제, 스크립트 실행, Git pull·merge·rebase·commit·push는 하지 않았다. Git 설정 파일도 바꾸지 않았다.

부모 `projects` HEAD는 `283ffc0e2b714ba9080e1719051816a44e1a9087`이고 GitHub `main`과 같다. 기록된 gitlink도 GitHub 클론과 같다.

| 경로 | 부모 gitlink | PC1에 체크아웃된 HEAD |
|------|----------------|------------------------|
| MEDI-IOT-EyeCare | `1c8bd4a7f86d3501958d3a62dcee4f8516d146a7` | `bb984a820362bfd0fd191945a54bf3134e09aca1`, 브랜치 `feature/mvp04c-security-hardening` |
| shared-libraries | `5bc2147cfb4151ab693efa3c8a80183c20fde5f9` | `95c1bb1d12f5eac7791a34a5a071c5567bc952c5`, `main` |
| AutoNoGaDa-ADK | `e180dd884f0f71b82e6ad05c25ae3d6293b2ae3e` | 같은 커밋, `main` |
| CoOps-Platform | `52150ea8120c7cbbe1bde4121842da9aa437eb56` | `1b18cce56656c617ad89ea4eae5053d4a125fd30`, `main` |

PC1 작업 트리에는 GitHub 클론의 최상위 목록에 없던 `eyecare-platform`, `medi-audit-engine`, `openclaw`, `paperclip`이 있다. `MEDI-SkinAI-Core`는 `.gitignore`에 있다. 이 디렉터리는 읽지 않고 이름만 확인했다. `docker-compose.dev.yml`의 Postgres 이미지는 `pgvector/pgvector:pg15`이고, `medi-iot-api`의 `PYTHONPATH`와 `alembic upgrade head` 기동은 005에서 본 GitHub 컴포즈와 같다. 컴포즈는 시작하지 않았다.

공유 인증 정책 파일은 PC1 체크아웃과 로컬 `bd7d353`, 핀 `5bc2147` 모두 임상 액션이 없었다. 임상 액션은 로컬 shared-libraries 클론에만 추가했다. 핀 커밋을 런타임 라이브러리로 바꾸어 테스트를 실행하지는 않았다.

## 7. 2026-10-23 PC2에서 확인한 부모 기준

이 절은 PC2 작업 메모다. 부모 문서의 사본이 아니다.

권위 위치는 `https://github.com/sangkny/projects.git` 이다. PC1 읽기 경로:

- `\\MEDIIOT-SKLEE\idea-collection\projects\PORT-ALLOCATION.md`
- `\\MEDIIOT-SKLEE\idea-collection\projects\docs\PLATFORM-ARCHITECTURE.md`
- `\\MEDIIOT-SKLEE\idea-collection\projects\docs\CROSS-PROJECT-INTEGRATION.md`

2026-10-23 08:56 KST에 PC1 `projects` HEAD는 `283ffc0e2b714ba9080e1719051816a44e1a9087` (`main`)이었다. 위 세 문서의 2026-10-23 내용은 커밋되지 않았다. GitHub `main`의 `PORT-ALLOCATION.md`는 2026-07-15 카탈로그이고, 아키텍처 두 파일은 GitHub `docs` 목록에 없다. 상태: `PENDING_PC1_PUBLICATION`. PC1 파일은 수정하지 않았다.

부모 아키텍처는 Clinical Query를 UNKNOWN으로 적는다. PC1이 연 트리에서 구현 파일을 찾지 못했기 때문이다. PC2 기능 커밋은 `1647b83b557abbc85d9778cfbf816d8aab3cf518`이다. 정책 커밋은 shared-libraries `a9d2dbd13df94d4be284c96c801f00dcff4f7956`이다. 그 사실을 부모 문서의 CONFIRMED로 바꾸려면 브랜치 게시 후의 별도 확인이 필요하다.

임상 문서가 이미 적는 내용과 부모 경계:

- Phase 006 통합 상태는 게시된 `feat/clinical-support-002` `a8661d5ab665f686b2e81ef9c0be1e8f633c8e93`과 이 문서 6절에 있다. 부모 서브모듈 포인터는 옮기지 않았다.
- Phase 007 질의와 품질 실행은 `1647b83b557abbc85d9778cfbf816d8aab3cf518`이다. 설명은 `docs/CLINICAL-QUERY-SPEC.md`와 임상 문서 진행 기록에 있다.
- 인증과 정책은 shared-libraries다. 로컬 클론은 `C:\Tools\downloads\phase005-inspect\shared-libraries`, 브랜치 `feat/clinical-query-quality-007`, 커밋 `a9d2dbd13df94d4be284c96c801f00dcff4f7956`이다. 기준은 `81a222baaa3ee256fe13fb33494ab2b6fd73ec76`이다. EYECARE 안에 정책을 복제하지 않는다.
- 임상 데이터 소유는 MEDI-IOT-EyeCare다. 연구·사이트 접근은 `StudySiteMember`다. 확정 관찰은 개정으로만 정정하고, 질의 해결은 그 값을 바꾸지 않는다.
- SVG-Analyzer는 분석 도구다. EYECARE나 LookScan의 런타임 의존성이 아니다.

저장소 책임은 부모 아키텍처와 같다. MEDI-IOT-EyeCare는 안과 영상·AI, 임상 연구, eCRF, Clinical Query, Data Quality Engine, 임상 감사와 보고를 소유한다. MEDI-SkinAI-Core는 피부 추론과 Appearance5, 체크포인트 검증, 종단 분석을 소유한다. LookScan은 소비자 촬영, Face Mesh, 선택적 SkinAI 후보, 스캔 이력, PBM 세션을 소유한다. shared-libraries는 공통 인증·인가와 공유 인터페이스를 소유한다.

### PC2 포트 스냅샷

2026-10-23 검사다. 서비스를 재시작하거나 배정을 바꾸지 않았다. 부모 표에 넣을 제안이며, 그 자체로 배정 문서가 아니다.

| 대상 | 호스트 | 상태 | 근거 |
|---|---|---|---|
| Docker 공개 포트 | SVG-SKLEE | 없음 | `docker ps -a` 컨테이너 0 |
| WSL `Ubuntu-24.04` | SVG-SKLEE | ACTIVE, TCP 53 resolver만 | `ss -lnt`. 프로젝트 서비스 없음 |
| SVG 18480–18499 | SVG-SKLEE | 리스너 없음. 요구 범위는 `config/port_requirements.json` | Windows Listen 목록. 부모 공유본은 RESERVED로 인용 |
| `E:\Office_Automation\port_allocation.md` | SVG-SKLEE | 파일 없음 | CLI 기본 경로와 불일치. 파일을 만들지 않음 |
| EYECARE compose 호스트 포트 | SVG-SKLEE | ACTIVE 없음 | 이 클론의 훈련 compose에 `ports`가 없고, 개발 compose는 부모 저장소에 있다. PC2에서 그 compose를 시작하지 않음 |
| PostgreSQL 55432, 55433 | 부모 기록 | TEMPORARY, 예약 아님 | 부모 공유본이 이미 삭제된 일회성으로 기록 |
| PostgreSQL 55434, 55436 | SVG-SKLEE | TEMPORARY, 현재 Listen 없음 | Phase 006·007 일회용 컨테이너. 삭제됨. 부모 표에는 아직 없음 |
| chrome `127.0.0.1:9222`, Code 루프백 | SVG-SKLEE | ACTIVE | 프로세스 이름만 확인. 프로젝트 배정으로 단정하지 않음. UNKNOWN |
| PC1에 적힌 8001, 5452, 8210, 8211, 1234 등 | MEDIIOT-SKLEE | PC2에서는 확인하지 않음 | PC2 Listen에 없음. PC1 실행 여부는 UNKNOWN |

부모 문서에 제안할 추가만 적는다. 기존 행은 바꾸지 않는다.

1. SVG-SKLEE 2026-10-23 스냅샷: Docker 공개 포트 없음, 18480–18499 비청취, 로컬 `E:\Office_Automation\port_allocation.md` 없음.
2. 55434와 55436은 PC2의 삭제된 일회성 PostgreSQL이며 예약이 아니다.
3. Clinical Query를 CONFIRMED로 바꾸기 전에 PC2 브랜치 게시를 기다린다.
