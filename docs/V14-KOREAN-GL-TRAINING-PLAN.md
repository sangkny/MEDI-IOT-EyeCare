# v14 한국인 녹내장 훈련 계획

> IRB: 국내 임상기관 승인 (2019) · 로컬 전용  
> 상태: 계획 단계 — v10c 한국인 검증 후 훈련 시작

---

## §1 목적 (한국인 NTG 특화)

서양·공개 데이터셋 중심으로 훈련된 v10c가 한국인 정상안압녹내장(NTG) 코호트에서 성능이 저하될 수 있습니다.  
국내 임상기관 IRB 승인 데이터(~1,400장)를 unified manifest에 통합해 **한국인 NTG 특화** v14를 훈련합니다.

---

## §2 v10c 검증 결과 (2026-07-08 실측)

| 항목 | 값 |
|------|-----|
| 스크립트 | `scripts/eval_korean_gl.py` |
| 출력 | `/dataset/korean_glaucoma_fundus/eval_v10c_korean.json` |
| 실행 | `bash scripts/run_eval_korean_gl_gpu.sh` |
| ONNX provider | **CPUExecutionProvider** (컨테이너에 CUDA EP 없음) |

### v10c 한국인 성능 (CPU eval)

| 지표 | 값 |
|------|-----|
| N | 300 |
| mean GL prob | **0.633** |
| detection@0.5 | **0.713** |
| AUC(severity, grade≥2 vs 1) | **0.660** |
| NTG mean prob (n=170) | **0.621** ← 핵심 약점 |
| POAG mean prob (n=119) | **0.655** |

### v14 목표

| 지표 | 목표 |
|------|------|
| NTG mean_prob | ≥ **0.700** |
| GL AUC(severity) | ≥ **0.750** |

### GPU 환경 비고 (2026-07-08 진단)

| 항목 | 상태 |
|------|------|
| `torch.cuda.is_available()` | **True** (TITAN X) |
| PyTorch cuDNN | 90100 (번들) |
| 호스트 `libcudnn.so.9` | 없음 · **so.8**만 ldconfig |
| ONNX Runtime providers | `CPUExecutionProvider`만 (CUDA EP 미설치) |
| **훈련** | PyTorch CUDA → **정상** |
| **eval** | ONNX RT CPU fallback → 결과 유효 |

진단: `bash scripts/diagnose_gpu_env.sh`

---

## §3 데이터 구성

| 소스 | 장수 | 비고 |
|------|------|------|
| unified_v10 (기존) | 27,546 | 공개 데이터 dedup |
| Korean GL Modified | ~600 | 컬러 안저, Grade 1–3 |
| Korean GL Origin (fundus) | ~800 | 시계열 포함 |
| **v14 합계 (예상)** | **~29,000** | `korean_clinical=true` 플래그 |

빌드:

```bash
python3 scripts/build_v14_manifest.py \
  --base training/manifests/unified_v10.json \
  --output training/manifests/unified_v14.json
```

---

## §4 훈련 설정

| 항목 | 값 |
|------|-----|
| 기반 체크포인트 | v10c (`models/retinal_v10c/best.pt`) |
| manifest | `unified_v14.json` |
| loss weights | dr=0.28, **gl=0.28**, amd=0.18, myo=0.18, multi=0.08 |
| epochs | 60 |
| warmup | 8 |
| preprocess | none (사전 CLAHE+224) |
| 한국인 split | seed=42 고정, train/val/test 70/15/15 |

---

## §5 성공 기준

| 지표 | 목표 |
|------|------|
| GL AUC (val) | ≥ **0.850** |
| composite | ≥ v10c (0.8842) 유지 또는 개선 |
| NTG 서브그룹 | 별도 AUC/민감도 측정 (한국인 val) |
| DR/AMD/MYO | v10c 대비 ±0.02 이내 회귀 없음 |

---

## §6 일정 (제안)

1. 전처리 완료 + `eval_korean_gl.py` → v10c 베이스라인
2. `build_v14_manifest.py` → GPU에서 manifest 검증
3. `start_v14_train.sh` (추후) — v10c fine-tune
4. ONNX export → comprehensive fast mode A/B

---

## 관련 문서

- `docs/MODEL-VERSION-HISTORY.md`
- `docs/DATASET-REGISTRY.md`
- `book/part7/ch41b-dataset-management.md`
