# MEDI-IOT-EyeCare — Cursor Agent 인수인계

> 최종 업데이트: **2026-06-14**  
> Git: **82a6e9f** → v10e 훈련 중 커밋 예정 · LM Studio **OFF**

---

## 현재 스냅샷

| 항목 | 값 |
|------|-----|
| **v10c** | composite **0.8842** · ✅ **운영** |
| **v10e** | composite **0.8790** · GL **0.821** · ❌ **미배포** (v2_cache 미반영) |
| **v10f** | 🔜 **계획** (v2_cache only, extra2 제외) |
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
| manifest | `training/manifests/unified_v10e.json` (extra2 merge) |
| 상태 | v2_cache 경로 미반영 → v2 효과 분리 불가 |
| 결과 | composite **0.8790** · GL **0.821** |

```bash
ssh smartvisionglobal@192.168.0.23 \
  "docker logs \$(docker ps -q --filter ancestor=medi-train:gpu) --tail 10"
```

## v10f (Option B — v2_cache only, extra2 제외)

목적: extra2 변수를 제거하고 **v2_cache 전처리 효과만** 분리 검증.

### Step 1 — manifest 생성

```bash
docker run --rm --entrypoint bash \
  -v ~/workspace/dataset:/dataset \
  -v ~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare/data:/data_dr \
  -v ~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare:/workspace \
  medi-train:gpu -c '
    python3 /workspace/scripts/build_v10f_manifest.py
  '
```

### Step 2 — 훈련 시작

```bash
V10F=1 bash scripts/start_v10_train.sh &
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
