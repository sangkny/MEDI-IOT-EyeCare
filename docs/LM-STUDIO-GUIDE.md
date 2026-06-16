# LM Studio 모델 관리 가이드

> SSOT: `projects/docs/NETWORK-GUIDE.md` · 테스트 env: `.env.test`

## 원칙

| 상황 | 로드 모델 | VRAM |
|------|-----------|------|
| **개발·일상 코딩** | `google/gemma-4-e4b` + `nomic-embed` | ~4GB + embed |
| **unit/smoke/quick pytest** | **로드 불필요** (`AGENT_FOUR_AGENT_MOCK=1`) | 0 |
| **slow pytest / 실연동** | `gemma-4-e4b` only (`.env.test`) | ~4GB |
| **slow-26b pytest** | `gemma-4-26b` (명시적 opt-in) | ~18GB |
| **프로덕션 보고서** | `gemma-4-26b` (HEAVY) + e4b + embed | ~18GB + 4GB |

**개발 PC가 느려지면** LM Studio에서 **26b Eject** → e4b만 유지.

## 포트·URL

| 환경 | URL |
|------|-----|
| LM Studio (호스트) | `http://192.168.0.12:1234/v1` |
| Docker 컨테이너 | `http://host.docker.internal:1234/v1` |
| WSL pytest | `http://192.168.0.12:1234/v1` |

Serve on Local Network **항상 활성화**. SVG-Stock `:8000` 과 충돌 — LM Studio는 **1234** 고정.

## 테스트 env (`.env.test`)

```bash
LOCAL_FAST_MODEL=google/gemma-4-e4b
LOCAL_HEAVY_MODEL=google/gemma-4-e4b   # 테스트 중 26b 사용 금지
MEDI_USE_26B=0
AGENT_FOUR_AGENT_MOCK=1                # unit/smoke — LLM 미호출
```

회귀 실행:

```bash
./scripts/medi-regression.sh quick      # ~15min, LLM·slow 제외 (일상 권장)
./scripts/medi-regression.sh unit       # ~2min, LM Studio 불필요
./scripts/medi-regression.sh smoke      # ~5min, API + LLM mock
./scripts/medi-regression.sh full-mock  # ~60min, not slow 전체 · LLM mock
./scripts/medi-regression.sh slow       # ~30min, e4b 실연동 (MEDI_USE_26B=0)
./scripts/medi-regression.sh slow-26b   # ~60min+, 26b 실연동 (명시적 opt-in)
```

`full` 은 **`full-mock` 별칭** (WARN 출력). **`docker exec ... pytest -m "not slow"` 직접 실행 금지**.

## 26b (HEAVY) 사용 시점

- **테스트**: `./scripts/medi-regression.sh slow-26b` 또는 `MEDI_USE_26B=1`
- `/lab/fundus/report` AutoNoGaDa CONSENSUS 최종 검토
- 프로덕션 VISION 분석 (안과 이미지 고품질)

**운영 opt-in** — `.env.local` / `.env.prod` 에만:

```bash
MEDI_USE_26B=1
LOCAL_HEAVY_MODEL=google/gemma-4-26b-a4b
LOCAL_VISION_MODEL=google/gemma-4-26b-a4b
MEDI_VISION_MODELS=google/gemma-4-26b-a4b,mistralai/mistral-7b-instruct-v0.3
```

**개발 compose 기본값은 e4b** — 26b는 위 env 로만 opt-in. 테스트·개발은 `.env.test` + `quick`/`unit`/`smoke`/`full-mock`.

## 체크리스트

1. LM Studio → **26b Unload/Eject** (개발·테스트 시작 전)
2. `gemma-4-e4b` + `nomic-embed` 로드 확인
3. `curl http://192.168.0.12:1234/v1/models` → 200
4. `bash scripts/medi-regression.sh quick` (또는 `unit`)
