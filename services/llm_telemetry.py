"""
LLM 호출량 집계 (Redis)

대시보드 GET /dashboard/llm-usage 용도.
Orchestrator Lore, 단일 chat(), embed 요청별로 근삿값 저장.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import redis.asyncio as aioredis

from llm.base import EmbedResponse, LLMResponse

from config import get_settings

log = logging.getLogger("services.llm_telemetry")

_PREFIX = "medi:telemetry:llm"
_DAY_TTL_SEC = 35 * 24 * 3600


def _utc_date_string() -> str:
    return datetime.now(timezone.utc).date().isoformat()


async def _client() -> aioredis.Redis:
    settings = get_settings()
    return await aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=3,
        socket_timeout=3,
    )


async def shutdown_client(r: aioredis.Redis) -> None:
    await r.aclose()


def estimate_tokens_chat_response(res: LLMResponse) -> int:
    """Provider가 토큰을 주지 않을 때 문자 기반 근사."""
    if res.total_tokens > 0:
        return res.total_tokens
    return max(int(len(res.content or "") / 4) + 400, 200)


def estimate_tokens_embed(text_len: int) -> int:
    return max(int(text_len / 4) + 50, 32)


def _tokens_from_orchestrator_lore_decision(decision: str, model_used: str) -> int:
    """Lore 항목당 대략적 토큰 (감사/대시보드 용 근삿값)."""
    base = 300 + len(decision or "")
    m = model_used.lower() if model_used else ""
    if "heavy" in m or "26b" in m or "vision" in m or "large" in m:
        base += 600
    elif "gemma-4-e4b" in m or "e4b" in m:
        base += 200
    return max(base, 320)


async def incr_llm_counters(
    provider: str,
    *,
    tokens: int,
    calls: int = 1,
    day_str: str | None = None,
) -> None:
    """금일 호출수·추정 토큰 누적 (설정된 LLM provider 기준 bucket)."""
    if calls <= 0 and tokens <= 0:
        return
    ds = day_str or _utc_date_string()
    prov_slug = provider.lower().replace(" ", "_")
    agg_key = f"{_PREFIX}:g:{ds}"
    p_key = f"{_PREFIX}:p:{ds}:{prov_slug}"

    r = await _client()
    try:
        pipe = r.pipeline(transaction=True)
        if calls:
            pipe.hincrby(agg_key, "calls", calls)
            pipe.hincrby(p_key, "calls", calls)
        if tokens:
            pipe.hincrby(agg_key, "tokens", tokens)
            pipe.hincrby(p_key, "tokens", tokens)
        pipe.expire(agg_key, _DAY_TTL_SEC)
        pipe.expire(p_key, _DAY_TTL_SEC)
        await pipe.execute()
    except Exception as e:
        log.warning(f"[telemetry] incr 실패: {e}")
    finally:
        await r.aclose()


async def record_llm_chat_response(response: LLMResponse) -> None:
    tokens = estimate_tokens_chat_response(response)
    prov = response.provider.value if response.provider else "unknown"
    await incr_llm_counters(prov, tokens=tokens)


async def record_embedding_response(embed_resp: EmbedResponse, text_sample: str) -> None:
    tokens = estimate_tokens_embed(len(text_sample))
    prov = embed_resp.provider.value if embed_resp.provider else "unknown"
    await incr_llm_counters(prov, tokens=tokens)


async def record_from_orchestrator_lore(lore_entries: list) -> None:
    """OrchestratorResult.lore 항목마다 호출 수·토큰 누적."""
    if not lore_entries:
        return
    provider = get_settings().llm_provider
    tokens_sum = calls = 0
    for entry in lore_entries:
        decision = getattr(entry, "decision", "") or ""
        model_used = getattr(entry, "model_used", "") or ""
        tokens_sum += _tokens_from_orchestrator_lore_decision(decision, model_used)
        calls += 1
    await incr_llm_counters(provider, tokens=tokens_sum, calls=calls)


async def get_daily_llm_usage(day_str: str | None = None) -> dict[str, object]:
    """금일(or 지정 일) 통계 및 provider bucket 목록."""
    ds = day_str or _utc_date_string()
    r = await _client()
    try:
        gkey = f"{_PREFIX}:g:{ds}"
        raw = await r.hgetall(gkey)
        total_calls = int(raw.get("calls", 0) or 0)
        total_tokens = int(raw.get("tokens", 0) or 0)

        by_provider: list[dict[str, object]] = []
        prov_pattern = f"{_PREFIX}:p:{ds}:*"
        cursor: int | str = 0
        keys: list[str] = []
        while True:
            cursor, batch = await r.scan(cursor=cursor, match=prov_pattern, count=64)
            keys.extend(batch)
            if cursor in (0, "0"):
                break

        for pk in sorted(keys):
            suffix = pk.split(f"{_PREFIX}:p:{ds}:")
            pname = suffix[-1] if len(suffix) > 1 else pk
            h = await r.hgetall(pk)
            pc = int(h.get("calls", 0) or 0)
            pt = int(h.get("tokens", 0) or 0)
            if pc or pt:
                by_provider.append(
                    {"provider_key": pname, "calls_today": pc, "estimated_tokens": pt},
                )

        return {
            "date": ds,
            "calls_today": total_calls,
            "total_tokens_estimated": total_tokens,
            "by_provider": by_provider,
            "aggregation_note": (
                "Orchestrator는 Lore 항목 1건당 호출 1회로 집계. "
                "토큰 수는 Provider 미제공 시 문자 길이 기반 근삿값입니다."
            ),
        }
    except Exception as e:
        log.warning(f"[telemetry] 조회 실패: {e}")
        return {
            "date": ds,
            "calls_today": 0,
            "total_tokens_estimated": 0,
            "by_provider": [],
            "aggregation_note": f"telemetry_error: {e}",
        }
    finally:
        await r.aclose()
