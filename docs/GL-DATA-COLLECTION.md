# GL 데이터 수집 가이드

> **목표**: GL 11,725장 → **14,696장** (+2,971) · v10e 재훈련  
> **관련**: `docs/GL-IMPROVEMENT-HISTORY.md` · `scripts/download_gl_extra_datasets.sh`

---

## §1. 현재 GL 데이터 현황

### glaucoma_v2 (운영 독립 모델 · v10c GL 헤드 SSOT)

| 항목 | 값 |
|------|-----|
| 총량 | **~11,725장** |
| AUC (독립) | **0.946** |
| 소스 | G1020 · REFUGE · ORIGA · AIROGS · RIM-ONE (`Glaucoma_raw` + `Glaucoma_extra`) |
| manifest | `training/manifests/glaucoma_v2.json` |

### unified_v10 GL 라벨 (v10c 훈련)

GPU에서 live 통계 확인:

```bash
ssh smartvisionglobal@192.168.0.23 "
python3 -c \"
import json
m = json.load(open('workspace/Office_Automation/idea-collection/MEDI-IOT-EyeCare/training/manifests/unified_v10.json'))
gl = [s for s in m['samples'] if 'glaucoma' in s.get('available_labels',{})]
normal = [s for s in gl if s['available_labels']['glaucoma'] == 0]
abnormal = [s for s in gl if s['available_labels']['glaucoma'] == 1]
print(f'GL 전체: {len(gl)}')
print(f'  정상(0): {len(normal)}')
print(f'  이상(1): {len(abnormal)}')
print(f'  이상 비율: {len(abnormal)/len(gl)*100:.1f}%')
\"
"
```

> **참고 (2026-06-12)**: SSH 인증 미설정 시 GPU에서 직접 실행. v10 GL train 샘플 **~8,209장** (oversample 1.5× 대상).

---

## §2. 추가 수집 대상 (Glaucoma_extra2)

| 데이터셋 | 규모 | 라벨 | 수집 |
|----------|------|------|------|
| REFUGE | ~1,200 | glaucoma/normal | Grand-Challenge **수동** |
| G1020 | ~1,020 | glaucoma/normal | Kaggle |
| ORIGA | ~650 | glaucoma/normal | Kaggle |
| DRISHTI-GS | ~101 | glaucoma/normal | Kaggle |
| **합계** | **~2,971** | — | 11,725 → **14,696** (+25%) |

출력 경로: `$DATASET_ROOT/Glaucoma_extra2/{REFUGE,G1020,ORIGA,DRISHTI}/`

---

## §3. Kaggle API 설정

### GPU 서버 (192.168.0.23)

```bash
ssh smartvisionglobal@192.168.0.23 "
pip install kaggle --break-system-packages 2>/dev/null || pip install kaggle
kaggle --version
ls ~/.kaggle/ 2>/dev/null || echo 'kaggle.json 없음 → 설정 필요'
"
```

### kaggle.json 배치

1. [Kaggle Account → API](https://www.kaggle.com/settings) → **Create New Token**
2. GPU:

```bash
mkdir -p ~/.kaggle
chmod 700 ~/.kaggle
# kaggle.json 업로드 (username + key)
chmod 600 ~/.kaggle/kaggle.json
```

3. 검증: `kaggle datasets list | head`

> **2026-06-12**: Windows→GPU SSH `Permission denied` — 호스트키·공개키 등록 후 재시도.

---

## §4. 다운로드 절차

```bash
cd MEDI-IOT-EyeCare
export DATASET_ROOT=$HOME/workspace/dataset

# dry-run
bash scripts/download_gl_extra_datasets.sh --dry-run

# 실제 다운로드 (Kaggle 3종 + REFUGE 수동 안내)
bash scripts/download_gl_extra_datasets.sh
```

REFUGE 수동: https://refuge.grand-challenge.org → `$DATASET_ROOT/Glaucoma_extra2/REFUGE/`

---

## §5. 전처리 (preprocess_all.py)

```bash
# GPU Docker 또는 medi-train:gpu
python scripts/preprocess_all.py
```

| 원본 | 출력 |
|------|------|
| `/dataset/Glaucoma_extra2/REFUGE` | `resized_cache/Glaucoma_extra2/REFUGE` |
| `/dataset/Glaucoma_extra2/G1020` | `resized_cache/Glaucoma_extra2/G1020` |
| `/dataset/Glaucoma_extra2/ORIGA` | `resized_cache/Glaucoma_extra2/ORIGA` |
| `/dataset/Glaucoma_extra2/DRISHTI` | `resized_cache/Glaucoma_extra2/DRISHTI` |

CLAHE + 224×224 · JPEG q=95

---

## §6. manifest 재생성

```bash
# 1) glaucoma v3 (v2 소스 + extra2)
bash scripts/build_glaucoma_v3_manifest.sh

# 2) unified v10e
USE_GL_V3=1 bash scripts/build_v10_manifest.sh
# → training/manifests/unified_v10e.json
```

개별 extra2만:

```bash
bash scripts/build_glaucoma_extra2_manifest.sh
```

---

## §7. v10e 훈련 계획

```bash
V10E=1 bash scripts/start_v10_train.sh
```

| 파라미터 | v10c (운영) | **v10e (예정)** |
|----------|-------------|-----------------|
| OUTPUT | `retinal_v10c` | `retinal_v10e` |
| manifest | `unified_v10.json` | `unified_v10e.json` |
| gl_weight | **0.28** | **0.28** (최적값 유지) |
| gl_oversample | 1.0 | **1.0** (데이터 충분) |
| GL 데이터 | ~11,725 | **~14,696** |
| batch | 64 | 64 |
| warmup | 8 | 8 |

---

## §8. 예상 성능

| 지표 | v10c | v10e (목표) | 비고 |
|------|------|-------------|------|
| GL AUC | 0.835 | **0.860+** | 데이터 +25% |
| composite | 0.8842 | ≥0.884 | gl_w=0.28 유지 |
| fast 운영 | v10c + 앙상블 | v10e 검증 후 A/B | 앙상블 병행 |

v10d 교훈: **증강/오버샘플 < 데이터 규모** · v10e는 데이터 추가가 핵심.

배포 기준: composite ≥ v10c **且** GL AUC > 0.835 → ONNX export · A/B.

---

## 파이프라인 요약

```
download_gl_extra_datasets.sh
  → preprocess_all.py
  → build_glaucoma_v3_manifest.sh
  → USE_GL_V3=1 build_v10_manifest.sh
  → V10E=1 start_v10_train.sh
  → export_v10.py (검증 후)
```
