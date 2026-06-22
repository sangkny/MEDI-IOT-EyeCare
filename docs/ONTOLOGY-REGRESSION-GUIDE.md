# Ontology 회귀 가이드 — MEDI-IOT-EyeCare

> 최종 업데이트: 2026-06-22  
> 연계: `scripts/check-ontology-harness.sh` (idea-collection 메타) · `book/part7/ch26-medi-r3.md` §26.7

---

## §1 운영 ontology 경로 vs 훈련용 seg CDR

| 경로 | 입력 CDR | ontology 연동 | 상태 |
|------|----------|---------------|------|
| **운영** (`comprehensive_fundus.py`) | `ProbabilityBasedCDR` (CNN probability 근사) | `build_glaucoma_ontology_payload` → `validate_glaucoma_ontology` → `apply_four_agent_glaucoma_decision` | ✅ **운영 중** |
| **훈련** (`train_v10.py` v12/v13) | `cdr_from_seg_logits(seg_head)` | **미연동** | ⏸ 운영 연동 **보류** |
| **안전망** | `tests/test_seg_cdr_ontology_integration.py` | seg CDR → ontology **사전 검증** | ✅ CI·로컬 회귀 |

`SegmentationBasedCDR`는 `NotImplementedError` — seg 마스크 품질(≥70% 커버리지) 확보 전까지 운영 전환하지 않음.

---

## §2 Tier 0 체크리스트 (`check-ontology-harness.sh`)

**실행** (WSL, LM Studio 불필요, ~3~5분):

```bash
cd /mnt/e/Office_Automation/idea-collection
bash scripts/check-ontology-harness.sh
```

| 단계 | 내용 |
|------|------|
| **[1/3]** | shared-libs: `ontology/tests` + harness 구조 |
| **[2/3]** | medi-iot-api: vision_router, fhir, storage, auto_promote |
| **[3/3]** | (완료 메시지) Tier 0 통과 |

**권장 주기**

| 시점 | 실행 |
|------|------|
| **PR** (ontology/harness/MEDI 안저 변경) | 필수 |
| **주 1회** | 스케줄 또는 수동 |
| **모델 ONNX 교체** | §3 절차 추가 |

---

## §3 모델 ONNX 교체 (v10c → vN) 시 필수 회귀

1. **단위** (Docker `medi-iot-api`):

```bash
cd projects
docker compose -f docker-compose.dev.yml exec medi-iot-api \
  python -m pytest tests/test_glaucoma_cnn.py tests/test_cdr_estimator.py \
  tests/test_glaucoma_ontology_e2e.py tests/test_seg_cdr_ontology_integration.py -m unit -q
```

2. **Comprehensive E2E**:

```bash
python scripts/check_comprehensive_modes_e2e.py
```

3. **ontology_passed 스냅샷** — sklee 등 고정 fixture에서 `audit["ontology_passed"]`·`decision`·`risk_level`을 이전 배포와 비교 (수동 또는 스크립트 확장).

---

## §4 seg→ontology 갭 — 현재 상태·향후 계획

| 항목 | 상태 |
|------|------|
| v12/v13 seg_head | 훈련·`test_v12_seg_head.py`만 — **미배포** |
| ontology 게이트 | probability CDR만 사용 |
| 통합 테스트 | `test_seg_cdr_ontology_integration.py` — **연동 가능성** 사전 검증 |
| 향후 | `SegmentationBasedCDR` 구현 + 마스크 커버리지 ≥70% + inference 경로 연결 후 §3 회귀 재실행 |

**SSOT 성능**: v10c+앙상블 운영 유지 · v12/v13 deprioritize (`CURSOR_HANDOVER.md`).
