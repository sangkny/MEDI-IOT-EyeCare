# 안저 고품질 전처리 가이드

> **코드**: `services/fundus_enhancement.py`  
> **배치**: `scripts/preprocess_enhanced.py` → `enhanced_cache/`  
> **비교**: `scripts/compare_enhancement.py`  
> **실행**: Docker 필수 — `docs/DOCKER-POLICY.md`

---

## §1. 전처리 방법 비교

| 방법 | `EnhanceMode` | 효과 | 처리시간 | 적합 대상 |
|------|---------------|------|----------|-----------|
| CLAHE only | `clahe` | 국소 대비 | 빠름 (**현재 운영**) | 모든 이미지 |
| CLAHE+Unsharp | `clahe_unsharp` | 선명도 | 빠름 | 흐릿한 이미지 |
| DCP+CLAHE | `dcp_clahe` | 안개/뿌연 제거 | 중간 | 백내장·저품질 |
| **FULL** | `full` | DCP+CLAHE+Unsharp | 중간 | **GL 특화·v10e** |

출력 캐시: `resized_cache/` (CLAHE only) vs **`enhanced_cache/`** (FULL) — 분리 유지.

---

## §2. 논문 근거

| 논문 | 내용 |
|------|------|
| **IETK-Ret** (MICCAI 2020) | Pixel Color Amplification — Dice **+0.491** |
| **Dark Channel Prior** (He et al. 2009) | Dehazing SOTA — 안저 뿌연 제거 |

---

## §3. Docker 실행 방법

### 개발 PC — 비교 이미지

```powershell
docker exec medi-iot-api-dev python3 scripts/compare_enhancement.py `
  --image /app/fundus_right_sklee.jpg `
  --output /app/enhancement_comparison.png
```

### 개발 PC — 단위 테스트

```powershell
docker exec medi-iot-api-dev python -m pytest tests/test_fundus_enhancement.py -v
```

### GPU — enhanced_cache 배치

```bash
cd MEDI-IOT-EyeCare
bash scripts/run_preprocess_enhanced_gpu.sh
tail -f preprocess_enhanced.log
```

또는:

```bash
docker run --rm --shm-size=4g \
  -v ~/workspace/dataset:/dataset \
  -v $REPO/data:/data_dr \
  -v $REPO:/workspace \
  medi-train:gpu \
  bash -c 'python3 /workspace/scripts/preprocess_enhanced.py'
```

---

## §4. 파이프라인 연동 (v10e)

```
Glaucoma_extra2 다운로드 (run_kaggle_gl_download_gpu.sh)
  → preprocess_enhanced.py (enhanced_cache)
  → build_glaucoma_v3_manifest.sh
  → USE_GL_V3=1 build_v10_manifest.sh
  → V10E=1 start_v10_train.sh
```

---

## §5. 향후 계획

본인 dehazing 알고리즘 통합:

1. `EnhanceMode.CUSTOM` 추가
2. `services/fundus_enhancement.py` → `custom_dehaze()` 함수
3. A/B: `enhanced_cache` vs `resized_cache` GL AUC 비교

---

## 관련 문서

- `docs/GL-DATA-COLLECTION.md` — 데이터 수집
- `docs/DOCKER-POLICY.md` — 실행 환경 원칙
- `docs/GL-IMPROVEMENT-HISTORY.md` — v10 시리즈 이력
