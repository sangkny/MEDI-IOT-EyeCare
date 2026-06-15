# MEDI-IOT-EyeCare — Cursor Agent 인수인계

> 최종 업데이트: **2026-06-14**  
> Git: **82a6e9f** → v10e 훈련 중 커밋 예정 · LM Studio **OFF**

---

## 현재 스냅샷

| 항목 | 값 |
|------|-----|
| **v10c** | composite **0.8842** · ✅ **운영** |
| **v10e** | 🔄 **GPU 훈련 중** (unified_v10e · 21,454장) |
| v10e ep4 | GL **0.764** · composite **0.833** (상승 중) |
| **v2_cache** | ✅ 생성 완료 (GPU) |
| **앙상블** | fast GL **0.900+** (v10c+glaucoma_v2) |
| LM Studio | **OFF** (HDD 100%) |
| unit 회귀 | **256 passed** · 10 LLM 실패 (LM Studio OFF, 정상) |

### ⚠️ LM Studio 필요 시점

```
⚠️ LM Studio 켜주세요: port 1234, Serve on Local Network
```

- `POST /lab/fundus/report` · AutoNoGaDa · IRB 초안

---

## v10e 훈련 (GPU 192.168.0.23)

| 항목 | 값 |
|------|-----|
| manifest | `training/manifests/unified_v10e.json` (v2_cache) |
| samples | **21,454** train |
| 스크립트 | `V10E=1 bash scripts/start_v10_train.sh` |
| manifest 검증 | `python3 scripts/verify_v10e_manifest.py` |

```bash
ssh smartvisionglobal@192.168.0.23 \
  "docker logs \$(docker ps -q --filter ancestor=medi-train:gpu) --tail 10"
```

### v10e 완료 후

1. `export_v10.py` → ONNX · E2E
2. composite ≥ v10c **且** GL AUC ↑ → 배포 검토
3. `enhanced_cache` 삭제 (root)
4. v10e 배포 후 `resized_cache` 삭제

---

## API (v2 실시간 전처리)

| 엔드포인트 | 설명 |
|-----------|------|
| `?preprocess=v2` | CenterCrop+CLAHE+UnsharpRGB 실시간 |
| `?preprocess=enhanced` | v2 + local DCP |
| E2E sklee | GL prob ~0.6+ · `ensemble_v10c_v2` (v10c ONNX) |

```bash
docker exec medi-iot-api-dev python -m pytest tests/test_fundus_enhancement.py -v
```

---

## 개발 PC 병행 완료 (2026-06-14)

| # | 항목 | 상태 |
|---|------|------|
| 1 | `start_v10_train.sh` V10E manifest 고정 | ✅ |
| 2 | `preprocess=v2` comprehensive API | ✅ E2E 200 |
| 3 | `verify_v10e_manifest.py` | ✅ |
| 4 | 회귀 256+ (LLM 10 skip) | ✅ |
| 5 | 문서 MODEL/GL/HANDOVER | ✅ |

---

## 실행 환경

| 환경 | 실행 |
|------|------|
| 개발 PC | `docker exec medi-iot-api-dev python3 ...` |
| GPU | `docker run --entrypoint bash medi-train:gpu -c '...'` |
