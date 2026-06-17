# MEDI-IOT-EyeCare — Cursor Agent 인수인계

> 최종 업데이트: **2026-06-17**  
> Git: v12 seg head 커밋 예정 · LM Studio **OFF**

---

## v12 — Disc/Cup 보조 세그 헤드 (진행 중)

| 항목 | 상태 |
|------|-----|
| 코드 | `train_v10.py` seg_head · `build_disc_cup_masks.py` · `unified_v12.json` |
| 테스트 | `tests/test_v12_seg_head.py` **7 passed** (Docker) |
| GPU | G1020 마스크 생성 · smoke/본 훈련 — **SSH 후 실행** |
| SSOT | `docs/V12-DISC-CUP-SEGMENTATION.md` |

```bash
# GPU (docker run 중첩 금지)
bash scripts/run_check_g1020_labels_gpu.sh
bash scripts/run_build_disc_cup_masks_gpu.sh
bash scripts/run_build_v12_manifest_gpu.sh
docker run --rm --gpus all ... python3 training/train_v10.py --manifest unified_v12.json --smoke --seg-head --epochs 1
V12=1 bash scripts/start_v10_train.sh
```

---

## 현재 스냅샷 — v10 실험 **완료**

| 항목 | 값 |
|------|-----|
| **v10c** | composite **0.8842** · GL **0.835** · ✅ **운영** |
| **v10e** | composite 0.8790 · GL 0.821 · ❌ 미배포 (+extra2) |
| **v10f** | composite **0.8397** · GL **~0.783** · ❌ 미배포 (v2_cache) |
| **앙상블** | fast GL **0.900+** (v10c+glaucoma_v2) |
| **precise GL** | glaucoma_v2 AUC **0.946** |
| 회귀 | `medi-regression.sh quick` · **248 passed** |

### 실험 결론

1. **v10c 최우수** → 운영 유지 (변경 없음)
2. **v2_cache 훈련** 실패 — pretrained `retinal_v4.pt`가 resize 도메인 · v2(CenterCrop+Unsharp) 불일치
3. **extra2** 효과 없음 — 라벨/분포 이슈 추정
4. **GL 개선** = 앙상블 (v10c + glaucoma_v2)

| 버전 | composite | GL | 전처리 | 상태 |
|------|-----------|-----|--------|------|
| v10c | **0.8842** | **0.835** | resized_cache | ✅ 운영 |
| v10e | 0.8790 | 0.821 | resized + extra2 | ❌ |
| v10f | 0.8397 | ~0.783 | v2_cache | ❌ |

SSOT: `docs/GL-IMPROVEMENT-HISTORY.md` · `docs/MODEL-VERSION-HISTORY.md`

---

## GPU 캐시 정리 (디스크 확보)

| 경로 | 조치 |
|------|------|
| `/dataset/enhanced_cache` | **삭제 예정** |
| `/dataset/v2_cache` | **삭제 예정** (v10f 실패) |
| `/data_dr/v2_cache` | **삭제 예정** |
| `/dataset/resized_cache` | **유지** (v10c) |
| `/data_dr/resized_cache` | **유지** (v10c) |

> API `?preprocess=v2` 추론 코드는 유지. 훈련 캐시만 정리.

---

## 다음 우선순위

1. **SaMD 병원 협력** — LOI 발송 (`docs/HOSPITAL-PARTNERSHIP.md`)
2. **CoOps M1** — iOS EAS Build / TestFlight
3. **shared-libraries** — AutoNoGaDa 실사용 시나리오
4. **GL** — **v12** Disc/Cup seg head (구조 변경) 또는 v10c GL head FT

---

## v12 산출물 (코드 준비 · GPU 훈련 TBD)

| 항목 | 값 |
|------|-----|
| manifest | `unified_v12.json` (+ `disc_cup_mask`) |
| weights | `models/retinal_v12/` (훈련 후) |
| loss | 5-head v10c + seg CE **0.05** |
| 실행 | `V12=1 bash scripts/start_v10_train.sh` |

---

## v10f 산출물 (GPU)

| 항목 | 값 |
|------|-----|
| manifest | `unified_v10f.json` · v2_cache 100% |
| best | composite **0.8397** ep34 · early-stop ep46 |
| weights | `models/retinal_v10f/best.pt` (git 제외) |
| meta | `models/retinal_v10f/best.meta.json` |

---

## API

| 엔드포인트 | 설명 |
|-----------|------|
| `?mode=fast` | v10c ONNX + 앙상블 |
| `?mode=precise` | glaucoma_v2 등 5모델 |
| `?preprocess=v2` | 실시간 v2 (추론용 · 훈련 캐시와 별개) |

---

## 실행 환경

| 환경 | 실행 |
|------|------|
| 개발 PC | `docker exec medi-iot-api-dev python3 ...` |
| GPU | `docker run --entrypoint bash medi-train:gpu -c '...'` |
| 회귀 | `bash scripts/medi-regression.sh quick` |
