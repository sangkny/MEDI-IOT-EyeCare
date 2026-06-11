# MEDI-IOT-EyeCare — Cursor Agent 인수인계

> 최종 업데이트: 2026-06-11  
> **메타 HANDOVER**: `idea-collection/CURSOR_HANDOVER.md`

---

## 현재 스냅샷 (Git: `ad299a6`)

| 항목 | 값 |
|------|-----|
| unit | **142 passed** (`medi-iot-api-dev`) |
| v10c | composite **0.8842** · GL **0.835** · `gl_weight=0.28` |
| ONNX | `scripts/export_v10.py` only (5-head · `export_multidisease_v1.py` 금지) |
| fast | ~6s 콜드 / **0.34s** 웜 (`mode=fast` v10c) |
| precise | ~42s (`mode=precise` 5모델) |

### 운영 모델 (5질환 + v10c)

| 질환 | 모델 | 지표 |
|------|------|------|
| DR | retinal_v4 | QWK=0.8204 |
| GL | glaucoma_v2 | AUC=0.9460 |
| AMD | retinal_amd_v1 | AUC=0.9803 |
| MYO | retinal_myopia_v1 | AUC=0.9460 |
| Multi | multidisease_v1 | mAUC=0.9610 |
| **v10c fast** | retinal_v10.onnx | composite=0.8842 |

### API

| 엔드포인트 | 설명 |
|-----------|------|
| `POST /api/v1/lab/fundus/comprehensive?mode=fast` | v10c ONNX ~6s |
| `POST /api/v1/lab/fundus/comprehensive?mode=precise` | 5모델 ~42s |
| `POST /api/v1/lab/fundus/report` | AutoNoGaDa LLM 보고서 (~67s) |

---

## AutoNoGaDa 연동 ✅ (2026-06-11)

| 항목 | 경로 |
|------|------|
| 통합 | `services/autonogada_integration.py` |
| 보고서 | `ReportGenerator` CONSENSUS → LM Studio |
| LM Studio | `host.docker.internal:1234` (`projects/.env.local`) |
| 검증 | 보고서 생성 · `ontology=True` |

---

## GPU · Docker

| 항목 | 값 |
|------|-----|
| GPU 서버 | `192.168.0.23` · `origin/main` 동기화 ✅ |
| 디스크 | 54.86GB (정리 전 203.5GB) |
| DockerHub | `sangkny/medi-train:gpu-v1.0` · `cpu-v1.0` |
| SSOT | `docs/DOCKER-REGISTRY.md` |

---

## Dashboard E2E

- 체크리스트: `docs/BROWSER-E2E-CHECKLIST.md`
- 자동: `projects/dashboard/scripts/check-portal-e2e.mjs` (Vite `:5174` 필요)
- 수동: Windows `npm run dev` → http://localhost:5174

---

## 다음 우선순위

1. Dashboard Vite E2E 수동 확인
2. SaMD IRB — `generate_irb_draft.py` · ch45 §45.10.2
3. Partner E2E — `partner_e2e_inline.py`

---

## 빠른 시작

```bash
curl -s http://localhost:8001/health
docker exec medi-iot-api-dev python -m pytest tests/ -m unit --ignore=tests/test_auth.py -q
```
