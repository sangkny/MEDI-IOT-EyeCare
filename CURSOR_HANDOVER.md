# MEDI-IOT-EyeCare — Cursor Agent 인수인계

> 최종 업데이트: **2026-06-17**  
> Git: **e0c6146** → v10 실험 결론 문서 커밋 예정 · LM Studio **OFF**

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
4. **GL** — v10c GL head fine-tuning 검토 (옵션 B · `GL-IMPROVEMENT-HISTORY.md`)

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
