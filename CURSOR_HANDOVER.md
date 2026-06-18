# MEDI-IOT-EyeCare — Cursor Agent 인수인계

> 최종 업데이트: **2026-06-19**  
> Git: v13 SAM pseudo-mask 파이프라인 · LM Studio **OFF**

---

## v13 — SAM pseudo-mask (진행 중)

| 항목 | 상태 |
|------|-----|
| Option 3 | ❌ glaucoma_v2 ONNX **분류만** `(batch,)` |
| Phase 1 | SAM ViT-B + G1020 discLoc BBox → `generate_pseudo_masks_sam.py` |
| 파일럿 Dice | n=100 mean **0.544** → **본 훈련 보류** (OSAM Phase 2 필요) |
| manifest | `build_v13_manifest.py` → `unified_v13.json` (GL mask **70%+** 목표) |
| 훈련 | `V13=1` seg_weight **0.10** |
| SSOT | `docs/V13-SAM-PSEUDO-MASK.md` |

```bash
bash scripts/install_sam_gpu.sh
PHASE=g1020 bash scripts/run_generate_pseudo_masks_gpu.sh
bash scripts/run_eval_pseudo_masks_gpu.sh
PHASE=manifest bash scripts/run_generate_pseudo_masks_gpu.sh
bash scripts/run_build_v13_manifest_gpu.sh
V13=1 bash scripts/start_v10_train.sh
```

---

## 현재 스냅샷 — v10+v12 실험 **완료**

| 항목 | 값 |
|------|-----|
| **v10c** | composite **0.8842** · GL **0.835** · ✅ **운영** |
| **v12** | composite **0.8719** · GL **~0.829** · segDice **0.978** · ❌ **미배포** |
| **앙상블** | fast GL **0.900+** (v10c+glaucoma_v2) |
| **precise GL** | glaucoma_v2 AUC **0.946** |
| 회귀 | `medi-regression.sh quick` · **248 passed** |

### v10 시리즈 + v12 최종

| 버전 | GL | composite | 방법 | 상태 |
|------|-----|-----------|------|------|
| v10c | **0.835** | **0.8842** | resized_cache, gl_w=0.28 | ✅ 운영 |
| v10d | 0.833 | 0.8793 | GL증강+오버샘플 | ❌ |
| v10e | 0.821 | 0.8790 | +extra2 | ❌ |
| v10f | 0.783 | 0.8397 | v2_cache | ❌ |
| v12 | 0.829 | 0.8719 | +Disc/Cup seg_head | ❌ |

**v12 결론**: seg_head는 완벽 학습(segDice 0.978)했으나 GL/composite v10c 미달 → **마스크 8.7%**로 backbone prior 전달 부족.

SSOT: `docs/GL-IMPROVEMENT-HISTORY.md` · `docs/V12-DISC-CUP-SEGMENTATION.md`

---

## 다음 우선순위 (v13)

1. **SAM pseudo-mask** — G1020 품질 검증(Dice≥0.85) → GL 전체 → **v13** 훈련
2. **SaMD 병원 협력** — LOI
3. **CoOps M1** — iOS EAS Build
4. **Synology DS1522+** — CPU 추론 데모

---

## v12 산출물 (GPU)

| 항목 | 값 |
|------|-----|
| manifest | `unified_v12.json` |
| best | composite **0.8719** · GL **~0.829** · segDice **0.978** |
| weights | `models/retinal_v12/best.pt` (git 제외) |
| meta | `models/retinal_v12/best.meta.json` ✅ |
| peak mem | **7.69GB** (seg_head Conv 순서 수정 후 안전) |

---

## GPU 캐시 정리 (디스크 확보)

| 경로 | 조치 |
|------|------|
| `/dataset/enhanced_cache` | **삭제 예정** |
| `/dataset/v2_cache` | **삭제 예정** (v10f 실패) |
| `/data_dr/v2_cache` | **삭제 예정** |
| `/dataset/resized_cache` | **유지** (v10c) |
| `/data_dr/resized_cache` | **유지** (v10c) |

---

## v10f 산출물 (GPU, 참조)

| 항목 | 값 |
|------|-----|
| manifest | `unified_v10f.json` · v2_cache 100% |
| best | composite **0.8397** ep34 · early-stop ep46 |
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

WSL + `docker compose -f docker-compose.dev.yml` · GPU 훈련 = `medi-train:gpu` only
