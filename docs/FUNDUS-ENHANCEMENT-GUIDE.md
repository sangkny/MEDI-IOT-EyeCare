# 안저 고품질 전처리 가이드 (v2)

> **코드**: `services/fundus_enhancement.py`  
> **배치**: `scripts/preprocess_v2.py` → `v2_cache/`  
> **비교**: `scripts/compare_v2.py` · `compare_v3.py` · `compare_enhancement.py`  
> **실행**: Docker 필수 — `docs/DOCKER-POLICY.md`

---

## §1. v1 vs v2 비교

| 항목 | v1 (`resized_cache` / `enhanced_cache`) | v2 (`v2_cache`) |
|------|----------------------------------------|-----------------|
| Resize | 직접 224×224 → **원형 왜곡** | **CenterCrop** 후 resize |
| CLAHE | ✅ | ✅ |
| Unsharp | 전체/과도 | **RGB 선택** (σ=1.5, s=1.8) |
| DCP | 전체 이미지 (역효과) | **유두 국소** (옵션) |
| CDR | 비율 손상 위험 | **안저 원형 보존** |

v1 `EnhanceMode` enum은 **폐기**. v2는 `enhance_fundus(use_clahe=..., use_unsharp=..., use_dcp=...)` 옵션 방식.

---

## §2. v2 최종 설정 (선택 이유)

| 파라미터 | 값 | 이유 |
|----------|-----|------|
| `unsharp_sigma` | **1.5** | 혈관/시신경 경계 — 과도한 노이즈 없음 |
| `unsharp_strength` | **1.8** | Laplacian edge energy ↑, CDR 왜곡 없음 |
| `unsharp_channels` | **RGB** | R(혈관)+G(조직) 동시 강조 |
| `use_dcp` | **False** (기본) | 전체 DCP는 배경 역효과 — 고품질 시 유두만 |
| `size` | **224** | v10 훈련/추론 해상도 |

---

## §3. CenterCrop 중요성 (CDR 왜곡 방지)

안저 이미지는 **원형 FOV**. v1에서 가로·세로 비율이 다른 채 `cv2.resize(224,224)` 하면 **타원→원 왜곡** → CDR(컵/디스크 비) 학습·추론에 치명적.

v2: `center_crop_square()` — `min(H,W)` 기준 중앙 정사각형 → 224 resize.

---

## §4. 채널별 Unsharp 효과

| 채널 | 효과 |
|------|------|
| **R** | 혈관 강조 |
| **G** | 망막 조직/시신경 강조 |
| **B** | 효과 미미 (안저에서) |
| **RGB** | 혈관+조직 동시 강조 (**기본값**) |
| **RG** | R+G만 — B 노이즈 억제 |

경량 추론: `unsharp_channels='G'`. API `preprocess=enhanced`는 v2 + `use_dcp=True`.

---

## §5. 캐시 관리 정책

| 캐시 | 상태 | 조치 |
|------|------|------|
| `resized_cache/` | v10c 운영 중 | v10e 배포 후 삭제 |
| `enhanced_cache/` | v1 과도 전처리 | **삭제 예정** |
| **`v2_cache/`** | v10e 훈련용 | **생성 중** (GPU) |

전처리 완료 후:

```bash
EXTRA2_V2=1 bash scripts/run_build_v10e_manifest_gpu.sh
V10E=1 bash scripts/start_v10_train.sh
```

---

## §6. Docker 실행 방법

### 개발 PC — v1 vs v2 비교

```powershell
docker exec medi-iot-api-dev python3 scripts/compare_v2.py `
  --image fundus_right_sklee.jpg `
  --output /tmp/compare_v2.png
```

### 개발 PC — 채널 프리셋 비교

```powershell
docker exec medi-iot-api-dev python3 scripts/compare_v3.py `
  --image fundus_right_sklee.jpg `
  --output /tmp/compare_v3.png
```

### 개발 PC — 단위 테스트 (LM Studio 불필요)

```powershell
docker exec medi-iot-api-dev python -m pytest tests/test_fundus_enhancement.py -v
```

### GPU — v2_cache 배치

```bash
bash scripts/run_preprocess_v2_gpu.sh
tail -f preprocess_v2.log
```

### API 실시간 v2

```
POST /api/v1/lab/fundus/comprehensive?preprocess=v2
POST /api/v1/lab/fundus/comprehensive?preprocess=enhanced   # v2 + local DCP
```

---

## 관련 문서

- `docs/GL-DATA-COLLECTION.md` — GL extra2 + v2_cache
- `docs/DOCKER-POLICY.md` — 실행 환경 원칙
- `book/part7/ch44-v10-multitask-architecture.md` §44.3
