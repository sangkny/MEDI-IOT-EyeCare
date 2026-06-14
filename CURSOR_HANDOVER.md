# MEDI-IOT-EyeCare — Cursor Agent 인수인계

> 최종 업데이트: **2026-06-12**  
> **메타 HANDOVER**: `idea-collection/CURSOR_HANDOVER.md`

---

## 현재 스냅샷

| 항목 | 값 |
|------|-----|
| unit | **152 passed** (`pytest -m unit`, LLM mock) |
| smoke | **230 passed** (API + LLM mock) |
| **v10c** | composite **0.8842** · GL **0.835** · `gl_weight=0.28` · ✅ **운영** |
| **v10d** | composite **0.8793** · GL **0.833** (ep42) · ❌ **미배포** |
| **앙상블** | fast GL **0.900+** · sklee 0.605→**0.725** · `ensemble_v10c_v2` |
| ONNX | `scripts/export_v10.py` only |
| fast | v10c ONNX + 불확실 구간 glaucoma_v2 앙상블 |
| precise | ~42s (5모델) |
| LM Studio | `192.168.0.12:1234` · `docs/LM-STUDIO-GUIDE.md` |

### 운영 모델 (5질환 + v10c + 앙상블)

| 질환 | 모델 | 지표 |
|------|------|------|
| DR | retinal_v4 | QWK=0.8204 |
| GL | glaucoma_v2 | AUC=0.9460 |
| AMD | retinal_amd_v1 | AUC=0.9803 |
| MYO | retinal_myopia_v1 | AUC=0.9460 |
| Multi | multidisease_v1 | mAUC=0.9610 |
| **v10c fast** | retinal_v10.onnx | composite=0.8842 |
| **앙상블** | v10c + glaucoma_v2 | fast GL 0.900+ |

### API

| 엔드포인트 | 설명 |
|-----------|------|
| `POST /api/v1/lab/fundus/comprehensive?mode=fast` | v10c ONNX ~6s |
| `POST /api/v1/lab/fundus/comprehensive?mode=precise` | 5모델 ~42s |
| `POST /api/v1/lab/fundus/report` | AutoNoGaDa LLM 보고서 (~67s) |

---

## 2026-06-11 완료 ✅

| 영역 | 내용 |
|------|------|
| v10c 운영 | composite=0.8842 · GL=0.835 |
| LM Studio | 포트 **1234** (SVG-Stock `:8000` 충돌 해소) |
| AutoNoGaDa | 실연동 · `/lab/fundus/report` |
| Dashboard E2E | 양안 fast v10 · GradCAM · BilateralView · Fast/Precise · FHIR · Compare |
| Partner E2E | REGISTER → ANALYZE → FHIR (`partner_e2e_inline.py`) |
| IRB | `generate_irb_draft.py` · gemma-4-e4b · ch45 §45.10.2 |
| Docker | 203.5GB → 54.86GB (~149GB 절약) |
| DockerHub | `sangkny/medi-train:gpu-v1.0` · `cpu-v1.0` |

---

## AutoNoGaDa 연동 ✅

| 항목 | 경로 |
|------|------|
| 통합 | `services/autonogada_integration.py` |
| 보고서 | `ReportGenerator` CONSENSUS → LM Studio |
| LM Studio | `.env.local` · `host.docker.internal:1234` |
| Partner | `partner_e2e_inline.py` · audit_trail + FHIR Bundle |

---

## GPU · Docker

| 항목 | 값 |
|------|-----|
| GPU 서버 | `192.168.0.23` |
| 디스크 | 54.86GB (정리 전 203.5GB) |
| DockerHub | `sangkny/medi-train:gpu-v1.0` · `cpu-v1.0` |
| SSOT | `docs/DOCKER-REGISTRY.md` |

---

## GL 개선 결론 (2026-06-12)

- v10d &lt; v10c → **v10c 유지** · GL 증강/오버샘플 효과 미미
- **앙상블(Part D)** 로 GL 0.90+ 달성 — `docs/GL-IMPROVEMENT-HISTORY.md`
- 다음: REFUGE/G1020 데이터 수집 · SaMD 임상 fine-tuning · v10e 검토

## 다음 우선순위

1. **CoOps M1** iOS TestFlight 준비
2. **SaMD 병원 협력** — LOI 발송 (`docs/HOSPITAL-PARTNERSHIP.md`)
3. **GL 데이터 추가 수집** (REFUGE / G1020) → v10e 재훈련 검토
4. **shared-libraries PyPI** 패키지화 검토

---

## 빠른 시작

```bash
curl -s http://localhost:8001/health
docker compose -f ../docker-compose.dev.yml exec medi-iot-api python -m pytest tests/unit -q
```
