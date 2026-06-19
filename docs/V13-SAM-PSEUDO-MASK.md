# v13 SAM Pseudo-Mask — Disc/Cup 세그멘테이션

## 1. 배경

**v12 교훈**: GL 마스크 **8.7%** → segDice 0.978이나 GL/composite v10c 미달.

## 2. Option 검토

| Option | 결과 |
|--------|------|
| glaucoma_v2 ONNX | ❌ 분류만 |
| Phase 1 BBox SAM | ❌ mean Dice **0.544** |
| **Phase 2 OSAM** | DINOv2 + SAM point prompts — **진행 중** |

## 3. Phase 1 — BBox SAM (실패)

| 지표 | 값 |
|------|-----|
| mean Dice | **0.544** |
| Dice < 0.70 | **83%** |
| 판정 | v13 본 훈련 **보류** |

## 4. Phase 2 — OSAM-Fundus (DINOv2 + SAM)

```
G1020 GT 80장 참조 풀 → DINOv2 disc/cup/bg prototype
타겟 patch cosine matching → SAM point prompts (+ / −)
leave-one-out self-test (10장) → mean Dice ≥ 0.80 목표
```

| 구성 | 설명 |
|------|------|
| DINOv2 | `dinov2_vits14` (TITAN X 12GB) |
| SAM | ViT-B + point prompts |
| 참조 | G1020 GT 상위 **80**장 (면적 outlier 제외) |
| self-test | 타겟은 참조 풀에서 **제외** (leave-one-out) |

### 실행

```bash
bash scripts/check_dinov2_gpu.sh
LIMIT=10 bash scripts/run_osam_fewshot_gpu.sh

# Dice ≥ 0.80 통과 시
python3 scripts/generate_pseudo_masks_sam.py --method osam --target all_gl

bash scripts/run_build_v13_manifest_gpu.sh
V13=1 bash scripts/start_v10_train.sh
```

코드: `services/osam_fundus.py` · `scripts/generate_pseudo_masks_sam.py --method osam`

### Phase 2 결과

> GPU few-shot 실행 후 채움 (`run_osam_fewshot_gpu.sh`)

## 5. Plan B / C (Phase 2 미달 시)

| Plan | 내용 | 커버리지 |
|------|------|----------|
| **B** | ORIGA Masks_Square **651** + G1020 GT | **14.3%** |
| **C** | Med-SA fine-tune SAM on G1020 | 품질 최고 · 시간 큼 |

**원칙**: 품질 검증 없이 v13 본 훈련 **금지** (v12 교훈).

## 6. v13 훈련 (품질 통과 후)

| 항목 | 값 |
|------|-----|
| manifest | `unified_v13.json` |
| GL mask 목표 | **70%+** |
| seg_weight | **0.10** |
| 성공 기준 | composite·GL **≥ v10c** |

## 7. 주의

- pseudo-mask `.png` → git 제외
- Docker 중첩 run 금지
- 운영: **v10c + glaucoma_v2 앙상블** 유지
