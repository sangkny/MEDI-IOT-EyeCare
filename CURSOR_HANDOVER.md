# MEDI-IOT-EyeCare — Cursor Agent 인수인계

> 최종 업데이트: 2026-06-10  
> **3-플랫폼 통합 개요**: [`docs/PLATFORM-OVERVIEW.md`](docs/PLATFORM-OVERVIEW.md)  
> **메타 HANDOVER**: `idea-collection/CURSOR_HANDOVER.md`

---

## 현재 스냅샷 (2026-06-10)

| 항목 | 값 |
|------|-----|
| Git | `f92e39b`+ |
| unit | **134 passed** |
| 운영 5모델 | DR v4 · GL v2 · AMD v1 · MYO v1 · Multi v1 |
| **v10c fast** | composite **0.8842** · GL **0.835** · `retinal_v10.onnx` |
| ONNX export | `scripts/export_v10.py` (5-head · multidisease export 금지) |
| meta | `models/retinal_v10c.meta.json` · `retinal_v10.meta.json` |
| E2E | fast ~6s · `check_comprehensive_modes_e2e.py` ✅ |

---

## v10 계보

| 버전 | composite | GL AUC | gl_weight | 상태 |
|------|-----------|--------|-----------|------|
| v10 | 0.8818 | 0.804 | 0.20 | 참조 |
| v10b | 0.8726 | 0.841 | 0.35 | GL 과적합 |
| **v10c** | **0.8842** | **0.835** | **0.28** | ✅ 운영 |

---

## 다음 우선순위

1. Dashboard Portal 브라우저 E2E
2. SaMD 임상 준비 (ch45)
3. shared-libraries AutoNoGaDa 구현

---

## 빠른 시작

```bash
curl -s http://localhost:8001/health
python scripts/check_comprehensive_modes_e2e.py
PYTHONPATH=../shared-libraries:. python3 -m pytest tests/ -m unit --ignore=tests/test_auth.py -q
```
