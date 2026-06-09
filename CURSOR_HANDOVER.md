# MEDI-IOT-EyeCare — Cursor Agent 인수인계

> 최종 업데이트: 2026-06-09  
> **3-플랫폼 통합 개요**: [`docs/PLATFORM-OVERVIEW.md`](docs/PLATFORM-OVERVIEW.md)  
> **메타 HANDOVER**: `idea-collection/CURSOR_HANDOVER.md`

---

## 플랫폼 맥락 (3-in-1)

| 플랫폼 | 이 repo와의 관계 |
|--------|------------------|
| **MEDI-IOT-EyeCare** (본 repo) | 안과 AI · ONNX 추론 · SaMD |
| **AutoNoGaDa-ADK** | 본 프로젝트 코드·문서·훈련 스크립트 **생성·유지** |
| **CoOps-Platform** | 임상 리뷰 큐 · 모바일 결재 · Stripe · MEDI API 소비 |

공통 기반: `projects/shared-libraries/` (LLM · 4-agent · ontology · auth)

---

## 현재 스냅샷 (2026-06-09)

| 항목 | 값 |
|------|-----|
| Git | `15c6c77`+ |
| unit | **134 passed** |
| 운영 | DR v4 · GL v2 · AMD v1 · MYO v1 · Multi v1 |
| v10 fast | composite 0.8818 · `?mode=fast` |
| v10b | 🔄 GPU (`retinal_v10b` · GL weight 0.35) |
| API | `8001` · comprehensive fast/precise |
| Dashboard | `8090/dashboard/` (projects compose) |

---

## 빠른 시작

```bash
# health
curl -s http://localhost:8001/health

# comprehensive E2E
python scripts/check_comprehensive_modes_e2e.py

# unit
PYTHONPATH=../shared-libraries:. python3 -m pytest tests/ -m unit --ignore=tests/test_auth.py -q

# GPU v10b 모니터
ssh smartvisionglobal@192.168.0.23 'docker logs $(docker ps -q --filter ancestor=medi-train:gpu) --tail 10'
```

---

## 핵심 경로

| 항목 | 경로 |
|------|------|
| comprehensive API | `api/lab.py` · `services/comprehensive_fundus.py` |
| v10 ONNX | `services/v10_cnn.py` · `models/retinal_v10.onnx` (git 제외) |
| 훈련 | `training/train_v10.py` · `scripts/start_v10_train.sh` |
| GPU 검증 | `scripts/gpu_verify_v10b_env.sh` |
| 모델 계보 | idea-collection `book/part7/ch41-*.md` |

---

## AutoNoGaDa 실증 (본 프로젝트)

- 5질환 CNN 서비스·API·테스트 134개
- ch36~ch46 + PLATFORM-OVERVIEW + DOCKER-POLICY 문서
- manifest/훈련/전처리/ONNX 스크립트 전체
- v10 → v10b 파이프라인 (27,546장 · 56,535 전처리)

---

## 다음 우선순위

1. v10b 완료 → GL AUC ≥0.90 → ONNX export
2. SaMD 임상 500건 설계
3. CoOps M4 모바일 안저 촬영 연동
