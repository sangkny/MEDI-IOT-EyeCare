# Retinal 모델 버전 이력

> SSOT: `docs/GL-IMPROVEMENT-HISTORY.md` · v10 실험 **2026-06-17 종료**

## v10 시리즈 요약

| 버전 | 상태 | composite | GL AUC | 전처리 | 데이터 | 날짜 |
|------|------|-----------|--------|--------|--------|------|
| v10 | 참조 | 0.8818 | 0.804 | resized_cache | 기본 | 2026-05 |
| v10b | 미배포 | 0.8726 | 0.841 | resized_cache | gl_w=0.35 | 2026-06 |
| **v10c** | ✅ **운영** | **0.8842** | **0.835** | resized_cache | gl_w=0.28 | 2026-06 |
| v10d | 미배포 | 0.8793 | 0.833 | resized_cache | GL증강+oversample | 2026-06-12 |
| v10e | 미배포 | 0.8790 | 0.821 | resized_cache | +extra2 2,375 | 2026-06-14 |
| **v10f** | ❌ 미배포 | **0.8397** | **~0.783** | **v2_cache** | v2 only | **2026-06-17** |

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

## 운영 모델 (현재)

| 역할 | 아티팩트 | 지표 |
|------|----------|------|
| fast 멀티태스크 | `models/retinal_v10.onnx` (v10c) | composite 0.8842 |
| GL 앙상블 | v10c + glaucoma_v2 | fast GL 0.900+ |
| precise GL | glaucoma_v2 | AUC 0.946 |

## 캐시 정책 (GPU)

| 삭제 예정 | 유지 |
|-----------|------|
| `enhanced_cache`, `v2_cache` (`/dataset`, `/data_dr`) | `resized_cache` (v10c) |

---

## 한국인 임상 데이터 (추가 예정, v14)

| 데이터셋 | 환자수 | 안구수 | 특징 |
|---------|------|------|-----|
| Korean GL Modified | 173명 | ~300안 (컬러) | 안저사진만, 수정본 |
| Korean GL Origin | 173폴더 | ~400안 (컬러) | 안저+시야+OCT, 복수방문 ~60명 |
| 합계 추가 예정 | ~1,400장 | — | IRB 2019, 로컬 전용 |

- 전처리: `scripts/run_all_korean_gl_gpu.sh`
- manifest: `scripts/build_v14_manifest.py` → `unified_v14.json`
- 검증: `scripts/eval_korean_gl.py` → `eval_v10c_korean.json`
- 계획: `docs/V14-KOREAN-GL-TRAINING-PLAN.md`
