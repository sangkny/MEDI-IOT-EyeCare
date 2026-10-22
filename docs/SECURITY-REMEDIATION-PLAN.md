# P0 보안 조치 계획

> 작업: EYECARE-CLINICAL-SUPPORT-002. 코드 변경, 자격 증명 교체, 운영 데이터베이스 수정은 하지 않음.  
> 기준 커밋: `a5e2f71f98011ad52684bef62ded28432a5f8df0`  
> 비밀 값은 적지 않는다. 운영 프로세스에 기본값이 실제로 로드됐는지는 확인하지 않았다.

## 진행 기록

### 2026-10-22 22:42 KST — PC2 정책 브랜치 게시

- 작업 ID: PC2-CLINICAL-GIT-PUBLISH-001
- 시작: 2026-10-22T22:42:55+09:00
- 종료: 2026-10-22T22:45:21+09:00
- PC: SVG-SKLEE / PC2
- 저장소: shared-libraries `feat/medi-iot-clinical-policy`, 이전 HEAD `bd7d353f90328b8fecb31df897a8e74ecd5e0c43`, 커밋 `81a222baaa3ee256fe13fb33494ab2b6fd73ec76`
- push: origin 기능 브랜치만. main과 PC1 체크아웃은 유지
- 테스트: `tests/test_policy.py` 6 passed. doctor의 임상 작성과 staff의 임상 읽기, staff 작성 거절을 포함
- 남은 문제: 이 정책은 main에 병합되지 않음. 레거시 무인증 환자·IoT 경로는 그대로
- 다음 승인: shared-libraries 기능 브랜치 병합

### 2026-10-22 22:13 KST — Phase 006 임상 API 인증

- 작업 ID: EYECARE-CLINICAL-SUPPORT-006
- 시작: 2026-10-22T22:13:52+09:00
- 종료: 2026-10-22T22:26:48+09:00
- PC: SVG-SKLEE, 브랜치 `feat/clinical-support-002`, HEAD `a5e2f71f98011ad52684bef62ded28432a5f8df0`
- 결정: `/api/v1/clinical-support`는 `current_user_strict`와 `policy_require` 뒤에 사이트 멤버십을 검사한다. 토큰이 없으면 401, 정책 또는 멤버십이 없으면 403. 레거시 무인증 라우트는 임상 입구로 쓰지 않는다
- 테스트: 합성 SQLite에서 401, staff의 403, 다른 사용자 403 PASS. 운영 노출은 계속 미확인
- 남은 문제: 002의 무인증 환자·IoT·이미지 경로와 기본 비밀은 그대로다. 정책 변경은 shared-libraries 로컬 클론에만 있다
- 다음 승인: 그 정책 파일을 shared-libraries 저장소 커밋으로 승인

### 2026-10-22 21:45 KST — Phase 005 임상 API를 열지 않음

- 작업 ID: EYECARE-CLINICAL-SUPPORT-005
- 시작: 2026-10-22T21:45:27+09:00
- 종료: 2026-10-22T21:55:58+09:00
- PC: SVG-SKLEE, 브랜치 `feat/clinical-support-002`, HEAD `a5e2f71f98011ad52684bef62ded28432a5f8df0`
- 결정: shared-libraries `medi-iot` 정책에 임상 관찰 액션이 없다. 연구·사이트 멤버십은 EYECARE 서비스에서만 검사했다. 무인증 HTTP를 추가하지 않았다
- 테스트: 비구성원의 초안 작성은 `ClinicalRecordError`. 라우트 테스트는 대상 라우트가 없어 NOT_TESTED
- 남은 문제: 002의 무인증 환자·IoT·이미지 경로와 기본 비밀은 그대로다. 운영 노출은 계속 미확인
- 다음 승인: 임상 라우트 전에 shared-libraries 정책 변경과 `current_user_strict` 결합

### 2026-10-22 13:53 KST — Phase 003 보안 범위

- 시작 2026-10-22T13:50:18+09:00, 종료 2026-10-22T13:53:13+09:00, 경과 2분 55초, PC SVG-SKLEE
- HEAD `a5e2f71f98011ad52684bef62ded28432a5f8df0`
- 새 결함 없음. 004에서 전면 보안 리팩터를 하지 않고, 배포 게이트는 유지
- 자격 증명 교체와 운영 데이터 변환 없음
- 다음: 민감 기능 배포 전에 이 문서의 해당 항목을 다시 승인

### 2026-10-22 13:39 KST — Phase 002 보안 계획

- 무인증 경로, 평문 이름, 기본 비밀을 코드 결함으로 기록. 운영 노출은 미확인

## 1. 판정 기준

코드 결함은 이 저장소의 라우트 시그니처와 설정 기본값으로 확인한다. 운영 노출은 배포 환경의 환경 변수, 리버스 프록시, 네트워크 경계를 보지 않았으므로 모두 미확인이다. 악용 조건이 맞을 때만 코드 결함이 운영 사고로 이어진다.

## 2. 확인된 결함

### 2.1 환자 API 인증 없음

| 항목 | 내용 |
|------|------|
| 코드 심각도 | 높음 |
| 운영 노출 | 미확인 |
| 악용 조건 | API 프로세스가 인증 프록시 없이 도달 가능해야 한다. |
| 파일 | `api/patients.py` |
| 결함 | 등록, 조회, 목록, 비활성화, 검사 목록, 이력, 추이, 보고서가 `get_db`만 의존한다. |

영향 경로:

- `POST /api/v1/patients/`
- `GET /api/v1/patients/{id}`
- `GET /api/v1/patients`
- `DELETE /api/v1/patients/{id}`
- `GET /api/v1/patients/{id}/exams`
- `GET /api/v1/patients/{id}/history`
- `GET /api/v1/patients/{id}/trend`
- `GET /api/v1/patients/{id}/reports`

같은 조건의 인접 경로: `POST /api/v1/diagnosis/exam` (`api/diagnosis.py`). 인증이 있는 진단 생성 경로와 다르다.

### 2.2 IoT API 인증 없음

| 항목 | 내용 |
|------|------|
| 코드 심각도 | 높음 |
| 운영 노출 | 미확인 |
| 악용 조건 | IoT 라우트가 외부에서 호출 가능해야 한다. |
| 파일 | `api/iot.py`, `services/iot_gateway.py` |
| 결함 | 장치 등록, 측정 수신, HealthKit, Health Connect, 최신값, 웹소켓에 인증 의존성이 없다. 측정값은 프로세스 메모리에만 있다. |

영향 경로:

- `POST /api/v1/iot/devices/register`
- `POST /api/v1/iot/measurements`
- `POST /api/v1/iot/healthkit`
- `POST /api/v1/iot/health-connect`
- `GET /api/v1/iot/latest/{patient_id}`
- `GET /api/v1/iot/patients/{patient_id}/latest`
- `WS /api/v1/iot/stream/{patient_id}`

### 2.3 인가와 소유권 없음

| 항목 | 내용 |
|------|------|
| 코드 심각도 | 높음 |
| 운영 노출 | 미확인 |
| 악용 조건 | 인증을 추가한 뒤에도 임의의 인증 사용자가 모든 환자 행을 읽고 쓸 수 있다. `Patient`에 기관, 연구, 소유자 열이 없다. |
| 파일 | `models/medical.py`, `api/patients.py`, `api/iot.py` |

인증만 추가하면 이 결함은 남는다. 소유권은 임상 모듈의 `StudySite`와 사이트 구성원 연결이 생긴 뒤에 검사할 수 있다. 그 전까지의 P0은 역할 정책으로 읽고 쓰기를 나누고, 행 단위 소유권은 임상 스키마 승인 뒤에 넣는다.

인접 확인: `api/images.py`의 업로드와 조회 시그니처도 `get_db`만 사용한다. 환자 API와 같은 변경에서 함께 닫는다.

### 2.4 `name_encrypted`에 평문 저장

| 항목 | 내용 |
|------|------|
| 코드 심각도 | 높음 |
| 운영 노출 | 미확인. 운영 행에 실명이 있는지는 보지 않았다. |
| 악용 조건 | 환자 등록이 가능하고 데이터베이스를 읽을 수 있어야 한다. |
| 파일 | `api/patients.py` |
| 결함 | 등록 시 이름 인자를 `name_encrypted`에 그대로 넣는다. 같은 함수의 주석은 AES-256을 운영 할 일로 남긴다. `pii_encryption_enabled`는 이 쓰기를 바꾸지 않는다. |

### 2.5 기본 JWT 서명 키

| 항목 | 내용 |
|------|------|
| 코드 심각도 | 높음 |
| 운영 노출 | 미확인. 운영이 환경 변수로 덮어썼는지는 확인하지 않았다. |
| 악용 조건 | 프로세스가 저장소의 기본값을 쓰고, 공격자가 그 기본값으로 서명한 토큰을 인증된 라우트에 보낼 수 있어야 한다. |
| 파일 | `config.py` |

### 2.6 기본 데이터베이스 자격 증명

| 항목 | 내용 |
|------|------|
| 코드 심각도 | 중간 |
| 운영 노출 | 미확인 |
| 악용 조건 | 데이터베이스 포트가 도달 가능하고, 그 인스턴스가 저장소 기본 사용자와 비밀번호를 그대로 써야 한다. |
| 파일 | `config.py` |

공개 저장소에 개발용 기본 URL이 들어 있다. 값과 URL은 이 문서에 반복하지 않는다.

### 2.7 비밀 관리

| 항목 | 내용 |
|------|------|
| 코드 심각도 | 중간 |
| 운영 노출 | 추적 파일은 공개 저장소에 있다. 그 주소가 현재 살아 있는지는 미확인. |
| 파일 | `.gitignore`, `.env.test`, `.env.local`, `config.py` |
| 결함 | `.gitignore`는 `.env`만 무시한다. `.env.test`는 사설 IP의 LLM 주소를 담고, `.env.local`은 모델 상대 경로를 담는다. `.env.local`에서 자격 증명 형태의 값은 보이지 않았다. |

이력 재작성과 자동 키 교체는 이 계획에 넣지 않는다.

## 3. 코드 조치

구현은 별도 승인 뒤에 개발 브랜치에서만 한다.

1. `api/patients.py`, `api/diagnosis.py`의 검사 등록, `api/iot.py`, `api/images.py`에 `current_user_strict`를 붙인다.
2. 정책 이름은 기존 `policy_require("medi-iot", ...)` 를 따른다. 추가 이름은 `patient_read`, `patient_write`, `iot_read`, `iot_ingest`, `image_read`, `image_write`다. 정책 목록의 원본은 `shared-libraries`에 있으므로 그 저장소의 변경이 같은 릴리스에 포함돼야 한다.
3. 응답 스키마와 상태 코드 본문은 유지한다. 인증 실패는 401, 권한 실패는 403이다.
4. `config.py`에서 JWT 서명 키와 데이터베이스 URL의 실제 기본 문자열을 제거한다. 둘 다 환경 변수가 없으면 기동이 실패한다. 테스트는 저장소 밖 환경 변수나 로컬 무시 파일로만 공급한다.
5. `.env.test`의 사설 주소와 `.env.local`은 이후 커밋에서 추적 해제한다. 파일 삭제와 `git filter`는 하지 않는다. `.gitignore`에 두 이름을 추가한다.
6. 이름 암호화는 새 쓰기에만 적용한다. 암호문에는 버전 접두를 붙인다. 접두가 없는 기존 값은 평문으로 읽어 지금과 같이 마스킹한다. 운영 행의 일괄 변환은 별도 승인 작업이다.
7. IoT 메모리 저장은 인증 조치의 뒤에도 영속 저장소가 아니다. 임상 관찰의 원본으로 연결하지 않는다.

## 4. 기존 데이터 호환

- 환자, 검사, 진단, 이미지, 임상 연구 행은 삭제하거나 다시 쓰지 않는다.
- 평문 이름을 읽는 경로는 접두가 없을 때 현재 마스킹을 유지한다. 암호문만 기대하도록 바꾸면 기존 행의 표시가 깨진다.
- 데이터베이스 URL 기본값 제거 후, 환경 변수가 없는 로컬 compose는 기동에 실패한다. 개발 환경 파일은 저장소 밖에 둔다.
- 인증 추가 후 토큰 없는 기존 클라이언트와 아래 테스트는 401을 받는다.
  - `tests/test_e2e.py`
  - `tests/test_e2e_context.py`
  - `tests/test_e2e_week4_full_flow.py`
  - `tests/test_patient_history.py`
  - `tests/test_images.py`
- 이미 인증을 요구하는 임상 연구, FHIR, 대시보드, AI 진단 경로는 유지한다.

## 5. 회귀 테스트

운영 데이터베이스와 DeeVo에는 연결하지 않는다. 픽스처는 합성 환자만 사용한다.

- 토큰 없이 환자 쓰기와 읽기, 검사 등록, IoT 수신, 이미지 업로드는 401이다.
- 토큰이 있고 정책이 없으면 403이다.
- 정책이 있으면 기존 201과 200, 마스킹된 이름이 유지된다.
- `SECRET_KEY` 또는 `DATABASE_URL`이 없으면 설정 로드가 실패한다.
- 접두 없는 이름은 마스킹되고, 접두 있는 이름은 복호화 뒤에 마스킹된다.
- `tests/test_clinical.py`의 연구·검토 흐름은 기존 인증 픽스처로 통과한다.
- 품질 엔진 도입 뒤에는 관찰 값의 해시가 판정 전후에 같다.

## 6. 하지 않는 일

운영 자격 증명을 교체하지 않는다. 운영 데이터베이스를 수정하지 않는다. Git 이력을 다시 쓰지 않는다. DeeVo 데이터를 읽거나 쓰지 않는다.

## 7. Phase 003 결정

새 보안 결함은 없다. 002의 심각도, 악용 조건, 운영 노출 미확인은 유지한다.

003은 플랫폼 전면 보안 리팩터를 004에 넣지 않는다. 이 결정이 무인증 환자·IoT·이미지 경로와 기본 비밀, 평문 `name_encrypted`를 취소하지는 않는다. 새 임상 API는 인증과 연구·사이트 인가가 있을 때만 추가한다. 기존 무인증 라우트를 임상 데이터 입구로 쓰지 않는다. 민감 임상 기능의 배포는 이 문서의 해당 요구가 충족되기 전에 하지 않는다. 자격 증명 교체와 운영 데이터 변환은 계속 승인 밖이다.

## 8. Phase 005 접근 결정

임상 지원 HTTP 라우트는 추가하지 않았다. shared-libraries의 `current_user_strict`는 토큰을 검사하지만, `medi-iot` 정책에는 관찰 초안·확정·정정 액션이 없다. 그 액션을 넣으면 shared-libraries 변경이 된다. 사이트 멤버십은 EYECARE `StudySiteMember`로 서비스 안에서만 검사한다. 레거시 환자·IoT 라우트의 무인증 동작을 임상 입구로 가져오지 않았다.

## 9. Phase 006에서 연 임상 입구

`/api/v1/clinical-support`만 새 임상 입구다. 의존성은 shared-libraries의 `current_user_strict`와 `policy_require("medi-iot", ...)`다. 액션 이름은 기존 정책과 같이 밑줄 형태다. doctor에게 임상 읽기·작성·확정·정정·관리를 주고 staff에게는 임상 읽기만 준다. admin의 `*`는 유지한다. 정책이 허용해도 `StudySiteMember`가 아니면 서비스가 403에 해당하는 오류를 낸다. 이 정책 목록의 변경 파일은 shared-libraries 저장소 것이다. 레거시 환자·IoT·이미지 라우트는 이 단계에서 고치지 않았다.
