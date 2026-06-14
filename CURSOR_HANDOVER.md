# MEDI-IOT-EyeCare — Cursor Agent 인수인계

> 최종 업데이트: **2026-06-13**  
> Git: v10e v2 전처리 커밋 예정 · GPU **preprocess_v2.py** 진행 중 · LM Studio **OFF**

---

## 현재 스냅샷

| 항목 | 값 |
|------|-----|
| **v10c** | composite **0.8842** · GL **0.835** · ✅ **운영** (`resized_cache`) |
| **v10e** | v2_cache 생성 중 → 훈련 **대기** |
| **앙상블** | fast GL **0.900+** · sklee 0.605→**0.725** |
| LM Studio | **OFF** (HDD 100%) — LLM 작업 건너뜀 |
| GPU | `192.168.0.23` · `preprocess_v2.log` |

### ⚠️ LM Studio 필요 시점

아래 작업 시 LM Studio 켜주세요:

- `POST /api/v1/lab/fundus/report` (진단보고서)
- AutoNoGaDa `workflow.run()`
- IRB 연구계획서 생성

```
⚠️ LM Studio를 켜주세요: Windows에서 LM Studio 실행 → port 1234 → Serve on Local Network 활성화
```

---

## 전처리 v2 (2026-06-13)

| 항목 | 경로 |
|------|------|
| v2 파이프라인 | `services/fundus_enhancement.py` |
| v2_cache 배치 | `scripts/preprocess_v2.py` · `run_preprocess_v2_gpu.sh` |
| 비교 | `compare_v2.py` (v1 vs v2) · `compare_v3.py` (채널) |
| API | `?preprocess=v2` · `?preprocess=enhanced` (v2+local DCP) |
| 가이드 | `docs/FUNDUS-ENHANCEMENT-GUIDE.md` · ch44 §44.3 |

### 캐시 정리 계획

| 캐시 | 상태 | 조치 |
|------|------|------|
| `resized_cache` | v10c 운영 | v10e 배포 후 삭제 |
| `enhanced_cache` | v1 과도 | **삭제 예정** |
| **`v2_cache`** | 생성 중 | **v10e 훈련** |

### v10e 파이프라인 (전처리 완료 후)

```bash
# GPU 모니터링
ssh smartvisionglobal@192.168.0.23 \
  "tail -5 ~/workspace/.../MEDI-IOT-EyeCare/preprocess_v2.log"

EXTRA2_V2=1 bash scripts/run_build_v10e_manifest_gpu.sh
V10E=1 bash scripts/start_v10_train.sh
```

---

## API

| 엔드포인트 | 설명 |
|-----------|------|
| `POST .../fundus/comprehensive?mode=fast` | v10c ONNX ~6s |
| `POST .../fundus/comprehensive?preprocess=v2` | v2 실시간 전처리 |
| `POST .../fundus/comprehensive?preprocess=enhanced` | v2 + local DCP |
| `POST .../fundus/report` | AutoNoGaDa (**LM Studio 필요**) |

---

## GL 데이터 (v10e)

| 항목 | 값 |
|------|-----|
| GL 합계 | **14,100** (11,725 + extra2 2,375) |
| manifest | `unified_v10e.json` · `EXTRA2_V2=1` |
| 문서 | `docs/GL-DATA-COLLECTION.md` |

---

## 실행 환경 (Docker 필수)

| 환경 | 실행 |
|------|------|
| 개발 PC | `docker exec medi-iot-api-dev python3 ...` |
| GPU | `docker run --entrypoint bash medi-train:gpu -c '...'` |

**금지**: WSL/GPU 호스트 `python3` 직접 — `docs/DOCKER-POLICY.md`

---

## 빠른 시작

```bash
curl -s http://localhost:8001/health
docker exec medi-iot-api-dev python -m pytest tests/test_fundus_enhancement.py -v
```
