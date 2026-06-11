# LM Studio 모델 관리 가이드

> SSOT: `projects/docs/NETWORK-GUIDE.md` · 테스트 env: `.env.test`

## 원칙

| 상황 | 로드 모델 | VRAM |
|------|-----------|------|
| **개발·일상 코딩** | `google/gemma-4-e4b` + `nomic-embed` | ~4GB + embed |
| **unit/smoke pytest** | **로드 불필요** (`AGENT_FOUR_AGENT_MOCK=1`) | 0 |
| **slow pytest / 실연동** | `gemma-4-e4b` only (`.env.test`) | ~4GB |
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
AGENT_FOUR_AGENT_MOCK=1                # unit/smoke — LLM 미호출
```

회귀 실행:

```bash
./scripts/medi-regression.sh unit    # ~2분, LM Studio 불필요
./scripts/medi-regression.sh smoke   # ~5분, API + LLM mock
./scripts/medi-regression.sh slow    # ~30분, e4b 실연동
./scripts/medi-regression.sh full    # ~60분
```

## 26b (HEAVY) 사용 시점

- `/lab/fundus/report` AutoNoGaDa CONSENSUS 최종 검토
- 프로덕션 VISION 분석 (안과 이미지 고품질)

**선택**: 운영에서 HEAVY를 26b로 유지하려면 `.env.local` / `.env.prod` 에만:

```bash
LOCAL_HEAVY_MODEL=google/gemma-4-26b-a4b
```

테스트·개발은 `.env.test` 로 e4b 고정.

## 체크리스트

1. LM Studio → **26b Unload/Eject** (개발·테스트 시작 전)
2. `gemma-4-e4b` + `nomic-embed` 로드 확인
3. `curl http://192.168.0.12:1234/v1/models` → 200
4. `docker compose exec medi-iot-api-dev python -m pytest tests/ -m unit -q`
