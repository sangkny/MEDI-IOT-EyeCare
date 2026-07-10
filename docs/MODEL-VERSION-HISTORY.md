# Retinal 모델 버전 이력

> SSOT: `docs/GL-IMPROVEMENT-HISTORY.md` · **v15b 수정크롭 완료 2026-07-11**

## v10 시리즈 요약

| 버전 | 상태 | composite | GL AUC | 전처리 | 데이터 | 날짜 |
|------|------|-----------|--------|--------|--------|------|
| v10 | 참조 | 0.8818 | 0.804 | resized_cache | 기본 | 2026-05 |
| v10b | 미배포 | 0.8726 | 0.841 | resized_cache | gl_w=0.35 | 2026-06 |
| **v10c** | ✅ **운영** | **0.8842** | **0.835** | resized_cache | gl_w=0.28 | 2026-06 |
| v10d | 미배포 | 0.8793 | 0.833 | resized_cache | GL증강+oversample | 2026-06-12 |
| v10e | 미배포 | 0.8790 | 0.821 | resized_cache | +extra2 2,375 | 2026-06-14 |
| **v10f** | ❌ 미배포 | **0.8397** | **~0.783** | **v2_cache** | v2 only | **2026-06-17** |
| **v14** | ✅ **한국인 특화** | **0.8769** | **0.842** | resized_cache | +KR 699 · gl_os=2.0 | **2026-07-09** |
| v15 | 참조 | 0.803 | 0.832 | resized_cache | grade_head · 이전 크롭 | 2026-07-09 |
| **v15b** | ✅ **Grade 변별** | **0.811** | **0.840** | resized_cache | disc_peak_v2 · gradeQWK **0.600** | **2026-07-11** |

## 실험 결론 (2026-06-17)

- **v10c 최우수** → ONNX `retinal_v10.onnx` 운영 유지
- v10e (extra2) · v10f (v2_cache) 모두 v10c 미달 → **미배포 확정**
- v10f 하락 원인: `retinal_v4.pt` pretrained 도메인(resized) ≠ v2_cache 도메인
- GL fast **0.900+**: v10c + **glaucoma_v2** 앙상블 (`ensemble_v10c_v2`)
- precise GL: **glaucoma_v2** AUC **0.946**

## v10f (2026-06-17)

| 항목 | 값 |
|------|-----|
| manifest | `training/manifests/unified_v10f.json` |
| 생성 | `scripts/build_v10f_manifest.py` |
| best_composite | **0.8397** (ep34) |
| GL AUC | **~0.783** (peak 0.7831 ep45) |
| early-stop | ep46 |
| meta | `models/retinal_v10f/best.meta.json` |
| weights | GPU `models/retinal_v10f/best.pt` (git 제외) |
| ONNX | **미수행** |

```bash
V10F=1 bash scripts/start_v10_train.sh
```

## v10e (2026-06-14)

| 항목 | 값 |
|------|-----|
| manifest | `unified_v10e.json` |
| 전처리 | resized_cache (+extra2, v2_cache 미반영) |
| 결과 | composite **0.8790** · GL **0.821** |
| 실행 | `V10E=1 bash scripts/start_v10_train.sh` |

## v14 (2026-07-09) — 한국인 NTG 특화 ✅

| 항목 | 값 |
|------|-----|
| manifest | `unified_v14.json` (28,243 · korean_clinical 699) |
| best_composite | **0.8769** |
| GL AUC (공개 val) | **0.842** (+0.007 vs v10c) |
| gl_oversample | **2.0** |
| meta | `models/retinal_v14/best.meta.json` |
| ONNX | `retinal_v14.onnx` (export 후) |

**한국인 eval (2026-07-09, CPU ONNX)**

| 지표 | v10c | v14 |
|------|------|-----|
| NTG mean_prob | 0.665 | **0.842** |
| detection@0.5 | 0.983 | **1.000** |
| AUC(severity) | 0.677 | 0.602 |

**배포**: 한국인 검출 → v14 · Grade → v15b · 일반 → v10c · 정밀 → v10c+glaucoma_v2

```bash
V14=1 bash scripts/start_v10_train.sh
python3 scripts/eval_korean_gl.py --model models/retinal_v14.onnx \
  --out-json /dataset/korean_glaucoma_fundus/eval_v14_korean.json
```

## v15b (2026-07-11) — Grade 변별 · 수정크롭 ✅

| 항목 | 값 |
|------|-----|
| manifest | `unified_v15.json` |
| crop | `disc_peak_v2` 재전처리 (2026-07-10) |
| best_composite | **0.8110** (ep45) · early_stop ep57 |
| gradeQWK | **0.600** |
| GL AUC (공개) | **0.840** |
| NTG mean_prob | **0.842** |
| meta | `models/retinal_v15/best.meta.json` (version=`v15b`) |
| ONNX | `retinal_v15.onnx` · `scripts/export_v15_onnx_fix.py` |
| 계획 | `docs/V15-GRADE-TRAINING-PLAN.md` |

**한국인 eval 4종**

| 지표 | v10c | v14 | v15(이전) | **v15b** |
|------|------|-----|-----------|----------|
| mean_prob | 0.671 | 0.841 | 0.831 | **0.833** |
| detection@0.5 | 0.983 | **1.000** | 1.000 | 0.997 |
| AUC(severity) | 0.677 | 0.602 | 0.652 | 0.606 |
| NTG mean_prob | 0.665 | **0.842** | 0.832 | **0.842** |
| gradeQWK | — | — | 0.551 | **0.600** |
| GL AUC | 0.835 | 0.842 | 0.832 | **0.840** |
| composite | **0.884** | 0.877 | 0.803 | **0.811** |

크롭 효과: gradeQWK **+0.049** · GL AUC **+0.008** · composite **+0.008**. Grade SSOT = **gradeQWK** (AUC(severity)는 binary↔Grade 상관).

---

## 운영 모델 (현재)

| 역할 | 아티팩트 | 지표 |
|------|----------|------|
| fast 멀티태스크 (일반) | `models/retinal_v10.onnx` (v10c) | composite 0.8842 |
| fast 멀티태스크 (한국인 검출) | `models/retinal_v14.onnx` | NTG mean 0.842 · det 1.000 |
| fast 멀티태스크 (Grade) | `models/retinal_v15.onnx` (**v15b**) | gradeQWK 0.600 · GL 0.840 |
| GL 앙상블 | v10c + glaucoma_v2 | fast GL 0.900+ |
| precise GL | glaucoma_v2 | AUC 0.946 |

## 캐시 정책 (GPU)

| 삭제 예정 | 유지 |
|-----------|------|
| `enhanced_cache`, `v2_cache` (`/dataset`, `/data_dr`) | `resized_cache` (v10c) |

---

## 한국인 임상 데이터 (v14 반영 완료)

| 데이터셋 | 장수 | 특징 |
|---------|------|------|
| Korean GL (manifest) | **699** | IRB 2019 · `korean_clinical=true` |
| Korean GL Modified (전처리) | 300 컬러 | eval 기준 |
| Korean GL Origin (전처리) | 399 안저 | 시계열 ~60명 |

- manifest: `training/manifests/unified_v14.json`
- eval: `eval_v10c_korean.json` / `eval_v14_korean.json`
- 계획: `docs/V14-KOREAN-GL-TRAINING-PLAN.md` ✅
