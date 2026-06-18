# v13 SAM Pseudo-Mask — Disc/Cup 세그멘테이션

## 1. 배경 (2025–2026 연구)

| 접근 | 특징 | 우리 적용 |
|------|------|-----------|
| Vanilla SAM | BBox prompt도 disc/cup 품질 subpar | Phase 1 베이스라인 |
| **OSAM-Fundus** | DINOv2 + SAM, one-shot | 향후 Phase 2 |
| SAM2-SGP | support-set guided | 참고 |
| Med-SA | medical fine-tune SAM | 장기 |

**v12 교훈**: segDice 0.978이나 GL 마스크 **8.7%** → backbone prior 전달 부족 → **v13 목표 GL 마스크 70%+**

## 2. Option 검토 (2026-06-19)

| Option | 내용 | 결과 |
|--------|------|------|
| **3** | glaucoma_v2 ONNX → pseudo-mask | ❌ **분류만** `(batch,)` 출력 |
| **1** | SAM + G1020 discLoc BBox | ✅ **Phase 1 구현** |
| **2** | OSAM-Fundus (DINOv2+SAM) | 📋 Phase 2 |

```
glaucoma_v2.onnx: input [batch,3,224,224] → output [batch]  # Option 3 불가
```

## 3. 파이프라인

```
G1020 discLoc/json ──→ SAM ViT-B ──→ disc_cup_masks/pseudo/G1020/
GL manifest images ──→ auto BBox ──→ SAM ──→ disc_cup_masks/pseudo/manifest/
                                              ↓
                              build_v13_manifest.py → unified_v13.json
                                              ↓
                              V13=1 start_v10_train.sh (seg_w=0.10)
```

### 자동 disc BBox (Phase 2)

1. grayscale + Gaussian blur
2. 상위 밝기 percentile → centroid
3. 반경 = 이미지 짧은 변 × **18%**
4. cup BBox = disc BBox × **0.55** (SAM 2nd prompt)

## 4. 스크립트

| 스크립트 | 용도 |
|----------|------|
| `scripts/check_glaucoma_v2_onnx.py` | Option 3 확인 |
| `scripts/install_sam_gpu.sh` | SAM 설치 검증 |
| `scripts/generate_pseudo_masks_sam.py` | pseudo-mask 생성 |
| `scripts/evaluate_pseudo_mask_quality.py` | G1020 GT vs pseudo Dice |
| `scripts/build_v13_manifest.py` | unified_v13.json |
| `scripts/run_generate_pseudo_masks_gpu.sh` | GPU wrapper |

### GPU 실행

```bash
# SAM ViT-B checkpoint (~375MB)
mkdir -p ~/workspace/checkpoints
wget -q https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth \
  -O ~/workspace/checkpoints/sam_vit_b_01ec64.pth

bash scripts/install_sam_gpu.sh
PHASE=g1020 bash scripts/run_generate_pseudo_masks_gpu.sh
bash scripts/run_eval_pseudo_masks_gpu.sh

# GL 전체 pseudo (11,725)
PHASE=manifest bash scripts/run_generate_pseudo_masks_gpu.sh

bash scripts/run_build_v13_manifest_gpu.sh
V13=1 bash scripts/start_v10_train.sh
```

## 5. 품질 기준 · 파일럿 결과 (2026-06-19)

| Dice | 판정 |
|------|------|
| mean ≥ **0.85** | v13 훈련 사용 가능 |
| mean < **0.70** | SAM prompt/방식 개선 필요 |
| bad (Dice<0.7) 비율 | 10% 미만 목표 |

### G1020 파일럿 (SAM ViT-B + discLoc BBox, n=100)

| 지표 | 값 |
|------|-----|
| mean Dice | **0.544** |
| median Dice | 0.572 |
| Dice ≥ 0.85 | **2%** |
| Dice < 0.70 | **83%** |

**판정**: vanilla SAM Phase 1 품질 **미달** → GL 전체 pseudo-mask / v13 본 훈련 **보류**

**다음**: OSAM-Fundus(DINOv2+SAM) 또는 Med-SA fine-tune 검토. 파이프라인 코드는 유지.

## 6. v13 훈련 계획

| 항목 | v12 | v13 |
|------|-----|-----|
| manifest | unified_v12 | unified_v13 |
| GL mask % | 8.7% | **70%+** 목표 |
| seg_weight | 0.05 | **0.10** |
| 성공 기준 | — | composite·GL **≥ v10c** |

## 7. 주의

- SAM은 **GPU 서버** `medi-train:gpu` 에서만 (ViT-B ~2GB VRAM)
- pseudo-mask `.png` → **git 제외** (dataset 마운트)
- Docker **중첩 run 금지**
