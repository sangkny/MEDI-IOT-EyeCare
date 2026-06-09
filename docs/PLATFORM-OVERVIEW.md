# MEDI-IOT + AutoNoGaDa + CoOps — 통합 플랫폼 개요

> 최종 업데이트: 2026-06-09  
> SSOT: 세 플랫폼의 구조·관계·사업화 방향을 한 문서에 정리  
> 상세 책: `idea-collection/book/part1/ch01-platform-overview.md` · `book/part7/ch46-business-strategy.md`

---

## 1. 플랫폼 구조

### 1.1 공통 기반 (`shared-libraries`)

모든 플랫폼이 공유하는 핵심 라이브러리 (`projects/shared-libraries/`):

| 모듈 | 역할 |
|------|------|
| `llm/` | LLM 추상화 — LOCAL / OpenAI / Claude / Gemini / Azure (5 Provider) |
| `agents/` | 4-에이전트 프레임워크 — Plan → Generate → Review → Fix |
| `ontology/` | SemanticValidator · StructuralValidator · 7+ 도메인 룰 |
| `auth/` | JWT · RBAC · `require_role` |
| `saas/` | Billing · Stripe · Quota |
| `notifications/` | PushGateway (Expo / FCM / APNs) · Inbox |
| `harness/` | 통합 시나리오 · 회귀 테스트 |
| `observability/` | Prometheus 메트릭 · decision audit |

```
                    ┌─────────────────────┐
                    │   shared-libraries   │
                    │ LLM · Agents · Onto  │
                    └──────────┬──────────┘
           ┌───────────────────┼───────────────────┐
           ▼                   ▼                   ▼
   MEDI-IOT-EyeCare    AutoNoGaDa-ADK      CoOps-Platform
   (안과 AI 진단)       (코드·업무 자동화)    (팀 운영·결재)
```

### 1.2 플랫폼별 역할

| 플랫폼 | 역할 | 핵심 가치 | 포트 (dev) |
|--------|------|----------|------------|
| **MEDI-IOT-EyeCare** | 안과 AI 진단 · SaMD | **0.34초** 5질환 동시 진단 (v10 fast) | **8001** |
| **AutoNoGaDa-ADK** | 코드·오피스 자동화 | 반복 개발·문서·스크립트 제거 | **8002** |
| **CoOps-Platform** | 비즈니스 운영 자동화 | 결재·협업·청구·모바일 | **8003** |

**메타 repo**: `idea-collection` (책 · HANDOVER · 스크립트)  
**런타임 repo**: `projects/` (docker-compose.dev.yml · dashboard · submodule)

---

## 2. AutoNoGaDa — 상세

### 2.1 목적

> "지치지 않는 코딩·업무 조수" — 개발자와 직장인의 반복적·수동적 작업을  
> AI 4-에이전트(Planner → Generator → Reviewer → Fixer)가 자동 처리

### 2.2 현재 프로젝트 실증 사례 (2026-06)

#### 코드 자동화 (Cursor + 4-에이전트)

```
개발자 요청 → Planner(설계) → Generator(코드) → Reviewer(검토) → Fixer(수정) → 완성
```

| 사례 | 산출물 |
|------|--------|
| Glaucoma/AMD/Myopia API | `services/glaucoma_cnn.py`, `amd_cnn.py`, `myopia_cnn.py` |
| GradCAM++ 키 매핑 | `head` → `classifier.1` state_dict 자동 수정 |
| v10 훈련 | `V10BatchLabels` device 오류 · `eval_multidisease_mauc` |
| comprehensive | fast/precise 모드 · `inference_mode` 메타 |
| 테스트 | **134 unit** 자동 생성·유지 |

#### 문서 자동화

- ch36~ch46 책 챕터 (~250페이지)
- `MODEL-VERSION-HISTORY.md` · `DOCKER-POLICY.md` · `PORT-ALLOCATION.md`
- `CURSOR_HANDOVER.md` 세션간 컨텍스트 정리
- `SAMD-CHECKLIST.md` · SaMD ch45

#### 스크립트·파이프라인 자동화

| 유형 | 예시 |
|------|------|
| manifest | `build_*_manifest.sh` (DR/GL/AMD/MYO/Multi/v10) |
| 훈련 | `start_*_train.sh` · `V10B=1` GL weight 0.35 |
| 전처리 | `preprocess_all.py` — CLAHE+224 (**56,535장**) |
| ONNX | `export_*_v1.py` · `export_v10_onnx.py` |
| 운영 | `medi-regression.sh` · `git_commit_safe.sh` · `update_port_allocation.sh` |

**생산성**: 약 6개월 분량 개발·문서·훈련 인프라를 **수 주**에 완료 → 마케팅 실증 사례

### 2.3 단독 서비스 범위

1. **개발팀** — PR 리뷰 봇 · 테스트 자동 생성 · docstring/README · 리팩토링 제안
2. **오피스** — 엑셀/CSV 분석 · 이메일 초안 · 회의록 → 할 일 · 발표 자료
3. **파이프라인** — CI/CD 구성 · ETL · API 통합 코드 생성

---

## 3. CoOps — 상세

### 3.1 목적

> "AI 기반 회사 반장" — 팀 결재·협업·비용·성과를 하나의 플랫폼에서 자동 관리

### 3.2 핵심 기능 현황

| 기능 | 설명 | 상태 |
|------|------|------|
| 결재/승인 워크플로 | 모바일 앱 결재 · inbox | **R3 ✅** |
| 팀 협업 | 업무 배정·IR/Video/SNS 콘텐츠 | **R3 ✅** |
| 비용/청구 | Stripe Checkout · Portal · metered | **R3 ✅** |
| Push 알림 | FCM / APNs / Expo gateway | **R3 ✅** |
| MEDI 연동 | 진단 큐 · `GET /clinical/reviews` | **R3 ✅** |
| iOS TestFlight | — | M1 예정 |
| 오프라인 결재 | Action Queue | M3 예정 |
| 모바일 안저 촬영 | Fundus 카메라 | M4 예정 |

### 3.3 안과 병원 활용 예

| 시간 | 플랫폼 | 동작 |
|------|--------|------|
| 오전 | CoOps | "오늘 환자 23명, 긴급 검토 2건" |
| 진료 | MEDI-IOT | 안저 0.34초 · 5질환 · urgent 배지 |
| 자동화 | AutoNoGaDa | 진단서·FHIR 초안 · EMR 연동 코드 |
| 저녁 | CoOps | 월간 통계 · Stripe 청구 |

---

## 4. MEDI-IOT — 현재 상태 (2026-06-09)

| 항목 | 값 |
|------|-----|
| 운영 모델 | DR v4 · GL v2 · AMD v1 · MYO v1 · Multi v1 (**5모델**) |
| v10 fast | composite **0.8818** · 웜 **~340ms** |
| v10b | 🔄 GPU 훈련 중 (GL weight **0.35**) |
| API | `?mode=fast\|precise` · Dashboard Portal/Admin |
| unit | **134 passed** |
| SaMD | ch45 · 임상 500건 준비 |

---

## 5. 통합 시나리오

### 시나리오 1: 안과 의원

```
환자 내원 → (CoOps) 예약·접수
         → (MEDI-IOT) 안저 AI 0.34초
         → (AutoNoGaDa) 진단서·청구서 초안
         → (CoOps) 결제·기록
```

### 시나리오 2: 의료 AI 스타트업

```
모델 훈련 → (AutoNoGaDa) 코드·디버깅·문서
         → (MEDI-IOT) GPU v10/v10b · ONNX 배포
         → (AutoNoGaDa) SaMD 서류 초안
         → (CoOps) 팀·투자자 보고
```

### 시나리오 3: 일반 기업 (CoOps + AutoNoGaDa)

```
업무 요청 → (CoOps) 결재 워크플로
         → (AutoNoGaDa) 보고서·제안서
         → (CoOps) 비용·정산
         → (AutoNoGaDa) 성과 분석
```

---

## 6. 사업화 전략

### 6.1 수익 모델

| 플랜 | 대상 | 월 요금 | 포함 |
|------|------|---------|------|
| Starter | 개발자 개인 | $29 | AutoNoGaDa · LOCAL LLM |
| Team | 스타트업 5인 | $99 | AutoNoGaDa + CoOps |
| Clinic | 의원 | $500 | **3플랫폼 번들** |
| Hospital | 종합병원 | $2,000+ | 엔터프라이즈 · precise 모드 |
| Enterprise | 대기업 | 협의 | Azure 온프레미스 |

### 6.2 차별화

1. **LOCAL-FIRST** — LM Studio 무료 시작 · 의료/금융 보안
2. **3-in-1 번들** — 의료 AI + 코드 자동화 + 운영 관리
3. **4-에이전트 품질** — 단순 LLM 대비 검증·수정 루프
4. **SaMD 준비** — 경쟁사 대비 의료 AI + 자동화 통합

### 6.3 GTM 로드맵

| Phase | 기간 | 내용 |
|-------|------|------|
| 1 | 0~3개월 | AutoNoGaDa 오픈소스·개발자 커뮤니티 |
| 2 | 3~6개월 | CoOps + AutoNoGaDa SMB 번들 |
| 3 | 6~12개월 | MEDI-IOT Clinic 번들 · 병원 파일럿 |
| 4 | 12개월+ | SaMD 인증 → 일본/동남아 |

---

## 관련 문서

| 문서 | 위치 |
|------|------|
| Agent HANDOVER | `idea-collection/CURSOR_HANDOVER.md` |
| MEDI 모델 계보 | `docs/MODEL-VERSION-HISTORY.md` (idea-collection) |
| Docker 정책 | `docs/DOCKER-POLICY.md` (idea-collection) |
| shared-libraries | `projects/shared-libraries/CURSOR_HANDOVER.md` |
| 사업화 상세 | `book/part7/ch46-business-strategy.md` |
