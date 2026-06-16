# MEDI-IOT-EyeCare — Cursor Agent 인수인계

> 최종 업데이트: **2026-06-17**  
> Git: **e1b6776** → v10f 결과 문서 커밋 예정 · LM Studio **OFF**

---

## 현재 스냅샷

| 항목 | 값 |
|------|-----|
| **v10c** | composite **0.8842** · GL **0.835** · ✅ **운영** |
| **v10e** | composite **0.8790** · GL **0.821** · ❌ 미배포 |
| **v10f** | composite **0.8397** · GL **0.781** · ❌ **미배포** (v2_cache only) |
| **v2_cache** | ✅ 57,672장 · manifest 100% 교체 · **훈련 채택 ❌** |
| **앙상블** | fast GL **0.900+** (v10c+glaucoma_v2) |
| LM Studio | **OFF** |
| 회귀 | `medi-regression.sh quick` · **248 passed** (~26s) |

### 운영 확정 (2026-06-17)

**v10c (resized_cache) 유지** — v10e/v10f 모두 composite·GL 미달.

| 비교 | composite | GL AUC | 전처리 |
|------|-----------|--------|--------|
| v10c ✅ | **0.8842** | **0.835** | resized_cache |
| v10e ❌ | 0.8790 | 0.821 | resized + extra2 |
| v10f ❌ | 0.8397 | 0.781 | v2_cache only |

---

## v10f (Option B — 완료 2026-06-17)

| 항목 | 값 |
|------|-----|
| manifest | `training/manifests/unified_v10f.json` (v2_cache 100%) |
| 스크립트 | `scripts/build_v10f_manifest.py` · `V10F=1 start_v10_train.sh` |
| best | composite **0.8397** ep34 · GL **0.7806** |
| early-stop | ep46 |
| GPU 산출물 | `models/retinal_v10f/best.pt` (git 제외) |
| ONNX | **미수행** (미배포) |

```bash
# manifest 재생성
docker run --rm --entrypoint python3 \
  -v ~/workspace/dataset:/dataset \
  -v ~/workspace/.../MEDI-IOT-EyeCare/data:/data_dr \
  -v ~/workspace/.../MEDI-IOT-EyeCare:/workspace \
  medi-train:gpu /workspace/scripts/build_v10f_manifest.py
```

---

## v10e (참고)

| 항목 | 값 |
|------|-----|
| manifest | `unified_v10e.json` (extra2 merge) |
| 결과 | composite **0.8790** · GL **0.821** |
| 한계 | v2_cache 미반영 → v10f로 분리 검증 완료 |

---

## API (v2 실시간 전처리)

| 엔드포인트 | 설명 |
|-----------|------|
| `?preprocess=v2` | CenterCrop+CLAHE+UnsharpRGB 실시간 (추론용) |
| `?preprocess=enhanced` | v2 + local DCP |
| fast ONNX | **v10c** · `ensemble_v10c_v2` |

> 훈련 v2_cache ≠ 실시간 v2 API. 훈련 캐시 교체는 v10f 결과로 **채택하지 않음**.

---

## 실행 환경

| 환경 | 실행 |
|------|------|
| 개발 PC | `docker exec medi-iot-api-dev python3 ...` |
| GPU | `docker run --entrypoint bash medi-train:gpu -c '...'` |
| 회귀 | `bash scripts/medi-regression.sh quick` (LM Studio 불필요) |

SSOT: `docs/GL-IMPROVEMENT-HISTORY.md` · `docs/LM-STUDIO-GUIDE.md`
