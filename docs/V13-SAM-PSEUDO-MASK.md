# v13 SAM Pseudo-Mask — Disc/Cup 세그멘테이션

## 1. 배경

**v12 교훈**: GL 마스크 **8.7%** → segDice 0.978이나 GL/composite v10c 미달.

## 2. Option 검토

| Option | 결과 |
|--------|------|
| glaucoma_v2 ONNX | ❌ 분류만 |
| Phase 1 BBox SAM | ❌ mean Dice **0.544** |
| **Phase 2 OSAM** | DINOv2 + SAM — **few-shot 실패** (아래 §4) |

## 3. Phase 1 — BBox SAM (실패)

| 지표 | 값 |
|------|-----|
| mean Dice | **0.544** |
| Dice < 0.70 | **83%** |
| 판정 | v13 본 훈련 **보류** |

## 4. Phase 2 — OSAM-Fundus (DINOv2 + SAM)

```
G1020 GT 80장 참조 풀 → DINOv2 disc/cup/bg prototype
타겟 patch cosine matching → SAM box prompts (고해상도 안저)
leave-one-out self-test (10장) → mean Dice ≥ 0.80 목표
```

| 구성 | 설명 |
|------|------|
| DINOv2 | `dinov2_vits14` (TITAN X 12GB) — hub 로드 ✅ |
| SAM | ViT-B + **DINO-guided box** (point-only는 고해상도에서 실패) |
| 참조 | G1020 GT 상위 **80**장 (면적 outlier 제외) |
| self-test | 타겟은 참조 풀에서 **제외** (leave-one-out) |

### 실행

```bash
bash scripts/check_dinov2_gpu.sh
LIMIT=10 bash scripts/run_osam_fewshot_gpu.sh
```

코드: `services/osam_fundus.py` · `scripts/generate_pseudo_masks_sam.py --method osam`

### Phase 2 결과 (GPU 192.168.0.23 · 2026-06-19)

| 시도 | mean Dice | median | pass@0.80 | 판정 |
|------|-----------|--------|-----------|------|
| point prompts (v1) | **0.0445** | 0.0099 | 0/10 | cup 마스크 과대(84%) — 고해상도(2423×3004)에서 SAM point 실패 |
| DINO box + 1024px feature (`bfe6e40`) | **0.2723** | 0.2674 | 0/10 | Phase 1(0.544)보다 **낮음** — **v13 본 훈련 보류** |

**원인 요약**: G1020 안저 해상도·도메인에서 DINOv2 prototype 위치 추정이 discloc BBox 대비 불안정. `all_gl` pseudo-mask 생성 **실행 안 함**.

**다음**: §5 Plan B (ORIGA 651 + G1020 GT) 또는 Plan C (Med-SA fine-tune).

## 5. Plan B / C (Phase 2 미달 — **현재 경로**)

| Plan | 내용 | 커버리지 | 상태 |
|------|------|----------|------|
| **B** | ORIGA Masks_Square **651** + G1020 GT **1,020** | **14.3%** | **권장 다음 단계** — pseudo-mask 없이 실제 GT만 |
| **C** | Med-SA fine-tune SAM on G1020 | 품질 최고 · 시간 큼 | OSAM/BBox 모두 미달 시 |

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
