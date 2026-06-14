# GL 데이터 수집 가이드

> **목표**: GL **11,725** → **14,100** (+2,375 extra2) · v10e 재훈련  
> **관련**: `docs/GL-IMPROVEMENT-HISTORY.md` · `scripts/build_gl_extra2_manifest.py`

---

## §1. 현재 GL 데이터 현황 (2026-06-13)

### 기존 (glaucoma_v2 · unified_v10)

| 항목 | 값 |
|------|-----|
| 총량 | **11,725장** |
| AUC (독립 glaucoma_v2) | **0.946** |
| 소스 | G1020 · REFUGE · ORIGA · AIROGS · RIM-ONE |
| manifest | `glaucoma_v2.json` · `unified_v10.json` |

### extra2 확보 완료 (GPU `Glaucoma_extra2/`)

| 데이터셋 | 장수 | 정상 | 녹내장 | 라벨 |
|----------|------|------|--------|------|
| **G1020** | 1,020 | 724 | 296 | `G1020.csv` → `imageID`, `binaryLabels` |
| **ORIGA** | 650 | 482 | 168 | `OrigaList.csv` → `Filename`, `Glaucoma` |
| **ACRIMA** | 705 | 309 | 396 | 파일명 `_g_` 포함 = 1 |
| **합계** | **2,375** | **1,515** | **860** | — |

**통합**: 11,725 + 2,375 = **14,100 GL** (v10e 목표)

### 디렉터리 경로 (GPU 호스트)

| 소스 | 이미지 경로 | 라벨 파일 |
|------|-------------|-----------|
| G1020 | `Glaucoma_extra2/G1020/G1020/Images/` | `.../G1020/G1020.csv` |
| ORIGA | `Glaucoma_extra2/G1020/ORIGA/Images/` | `.../G1020/ORIGA/OrigaList.csv` |
| ACRIMA | `Glaucoma_extra2/ORIGA/ACRIMA/Images/` | 파일명 규칙 |

Docker 마운트: `-v ~/workspace/dataset:/dataset`

---

## §2. 라벨 파싱 규칙

### G1020

```csv
imageID,binaryLabels
image_0.jpg,0
image_1.jpg,1
```

→ `path`: `Glaucoma_extra2/G1020/G1020/Images/{imageID}`

### ORIGA

```csv
Filename,Glaucoma
001.jpg,0
```

→ `path`: `Glaucoma_extra2/G1020/ORIGA/Images/{Filename}`

### ACRIMA

- `*_g_*` 또는 `_g_` 포함 파일명 → **1** (녹내장)
- 그 외 → **0** (정상)

→ `path`: `Glaucoma_extra2/ORIGA/ACRIMA/Images/{filename}`

---

## §3. manifest 생성 (Docker 필수)

### STEP 1 — gl_extra2.json

```bash
docker run --rm \
  -v ~/workspace/dataset:/dataset \
  -v $REPO:/workspace \
  --entrypoint bash medi-train:gpu -c \
  'python3 /workspace/scripts/build_gl_extra2_manifest.py'
```

출력: `training/manifests/gl_extra2.json`

### STEP 2 — unified_v10e.json

```bash
docker run --rm \
  -v $REPO:/workspace \
  --entrypoint bash medi-train:gpu -c \
  'python3 /workspace/scripts/build_v10e_manifest.py'
```

또는 일괄:

```bash
bash scripts/run_build_v10e_manifest_gpu.sh
```

### enhanced_cache 경로 (전처리 후)

```bash
bash scripts/run_preprocess_enhanced_gpu.sh
EXTRA2_ENHANCED=1 bash scripts/run_build_v10e_manifest_gpu.sh
```

`--extra2-enhanced-paths` → extra2 샘플 path가 `enhanced_cache/Glaucoma_extra2/...`

---

## §4. Kaggle / 다운로드

ACRIMA·G1020·ORIGA는 **2026-06-13 GPU 확보 완료**.  
추가 REFUGE/DRISHTI: `scripts/run_kaggle_gl_download_gpu.sh`

---

## §5. 전처리 (v2)

| 캐시 | 스크립트 | 용도 | 상태 |
|------|----------|------|------|
| `resized_cache/` | `preprocess_all.py` | CLAHE only (v1 왜곡) | v10c 운영 → 삭제 예정 |
| `enhanced_cache/` | `preprocess_enhanced.py` | v1 DCP+FULL (과도) | **삭제 예정** |
| **`v2_cache/`** | **`preprocess_v2.py`** | **CenterCrop+CLAHE+Unsharp** | **v10e 훈련용 (생성 중)** |

```bash
# GPU v2_cache (백그라운드)
bash scripts/run_preprocess_v2_gpu.sh
tail -f preprocess_v2.log

# 진행 확인 (GPU SSH)
ssh smartvisionglobal@192.168.0.23 \
  "tail -5 ~/workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare/preprocess_v2.log"
```

`preprocess_v2.py`는 `services/fundus_enhancement.enhance_fundus()` import — Docker 내부 전용.

---

## §6. v10e 훈련

```bash
# manifest + enhanced 경로 준비 후
V10E=1 bash scripts/start_v10_train.sh
```

| 파라미터 | v10c | **v10e** |
|----------|------|----------|
| manifest | `unified_v10.json` | `unified_v10e.json` |
| GL 장수 | ~11,725 | **~14,100** |
| gl_weight | 0.28 | **0.28** |
| gl_oversample | 1.0 | **1.0** |
| preprocess | none (resized_cache) | none (**v2_cache**) |
| batch / warmup | 64 / 8 | 64 / 8 |

manifest v2 경로:

```bash
EXTRA2_V2=1 bash scripts/run_build_v10e_manifest_gpu.sh
```

---

## §7. 예상 성능

| 지표 | v10c | v10e 목표 |
|------|------|-----------|
| GL AUC | 0.835 | **0.860+** |
| composite | 0.8842 | ≥ 0.884 |

배포: composite ≥ v10c **且** GL AUC ↑ → ONNX · A/B · 앙상블 병행

---

## 파이프라인 요약

```
extra2 데이터 확보 ✅
  → run_preprocess_v2_gpu.sh (v2_cache 생성)
  → EXTRA2_V2=1 run_build_v10e_manifest_gpu.sh
  → V10E=1 start_v10_train.sh
  → (v10e 배포 후) enhanced_cache · resized_cache 삭제
```
