"""VISION multi-modal 라우팅 + CONSENSUS 병합 (D R3 D3).

환경 변수:
    MEDI_VISION_MODE              single | consensus (기본 single)
    MEDI_VISION_MODELS            콤마 구분 모델 ID (2개 이상이면 consensus 권장)
    MEDI_VISION_CONSENSUS_MIN_AGREE  ICD 합의 최소 표 수 (기본 2)

``model_used`` 반환 형식:
    - single: ``google/gemma-4-26b-a4b``
    - consensus: ``consensus(gemma-4-26b,mistral-7b,...)``

auto_promote (R2) 는 ``"consensus" in model_used`` 를 그대로 사용한다.
"""
from __future__ import annotations

import asyncio
import logging
import os
from collections import Counter
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from llm.base import LLMResponse, ModelRole
from llm.client import LLMClient

log = logging.getLogger("services.vision_router")

SEVERITY_RANK: dict[str, int] = {
    "normal": 0,
    "mild": 1,
    "moderate": 2,
    "severe": 3,
    "critical": 4,
}


@dataclass(frozen=True)
class VisionRoutingConfig:
    mode: str
    model_ids: tuple[str, ...]
    consensus_min_agree: int

    @property
    def is_consensus(self) -> bool:
        return self.mode == "consensus" and len(self.model_ids) >= 2


def load_vision_config() -> VisionRoutingConfig:
    mode = (os.getenv("MEDI_VISION_MODE") or "single").strip().lower()
    raw = (os.getenv("MEDI_VISION_MODELS") or "").strip()
    if raw:
        model_ids = tuple(m.strip() for m in raw.split(",") if m.strip())
    else:
        fallback = (
            os.getenv("LOCAL_VISION_MODEL")
            or os.getenv("MEDI_VISION_MODEL")
            or "google/gemma-4-26b-a4b"
        )
        model_ids = (fallback.strip(),)

    try:
        min_agree = int(os.getenv("MEDI_VISION_CONSENSUS_MIN_AGREE", "2"))
    except ValueError:
        min_agree = 2
    min_agree = max(1, min_agree)

    if len(model_ids) >= 2 and mode == "single":
        mode = "consensus"
    if mode == "consensus" and len(model_ids) < 2:
        mode = "single"

    return VisionRoutingConfig(
        mode=mode,
        model_ids=model_ids,
        consensus_min_agree=min_agree,
    )


def _short_model_name(model_id: str) -> str:
    """consensus(...) 라벨용 짧은 이름."""
    base = model_id.rsplit("/", 1)[-1]
    return base[:48]


def merge_consensus(
    parsed_list: list[dict[str, Any]],
    *,
    model_ids: tuple[str, ...],
    min_agree: int,
) -> dict[str, Any]:
    """여러 모델 파싱 결과를 CONSENSUS 로 병합 (Mock 0 단위 테스트 대상)."""
    if not parsed_list:
        raise ValueError("parsed_list 가 비어 있음")
    if len(parsed_list) == 1:
        out = dict(parsed_list[0])
        out["model_used"] = model_ids[0] if model_ids else out.get("model_used", "unknown")
        return out

    icd_votes = Counter(p.get("icd10_code") or "H57.9" for p in parsed_list)
    icd, icd_count = icd_votes.most_common(1)[0]

    agreeing = [p for p in parsed_list if (p.get("icd10_code") or "H57.9") == icd]
    if icd_count < min_agree:
        agreeing = sorted(
            parsed_list,
            key=lambda p: float(p.get("confidence") or 0.0),
            reverse=True,
        )[:1]
        icd = agreeing[0].get("icd10_code") or icd

    sev = max(
        (p.get("severity") or "mild" for p in agreeing),
        key=lambda s: SEVERITY_RANK.get(s, 1),
    )
    confs = [float(p.get("confidence") or 0.0) for p in agreeing]
    confidence = sum(confs) / len(confs) if confs else 0.7

    primary = agreeing[0]
    labels = ",".join(_short_model_name(m) for m in model_ids)
    return {
        "condition": primary.get("condition") or "eye_disorder",
        "condition_kr": primary.get("condition_kr") or "안과 질환",
        "icd10_code": icd,
        "severity": sev,
        "confidence": round(min(1.0, max(0.0, confidence)), 4),
        "model_used": f"consensus({labels})",
        "consensus_votes": icd_count,
        "consensus_models": len(parsed_list),
    }


class VisionRouter:
    """VISION 모델 라우팅 — single 또는 parallel consensus."""

    def __init__(
        self,
        config: VisionRoutingConfig | None = None,
        client: LLMClient | None = None,
    ) -> None:
        self.config = config or load_vision_config()
        self._client = client or LLMClient()
        log.info(
            "VisionRouter mode=%s models=%s min_agree=%s",
            self.config.mode,
            self.config.model_ids,
            self.config.consensus_min_agree,
        )

    async def chat_vision(
        self,
        prompt: str,
        *,
        role: ModelRole = ModelRole.VISION,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.4,
    ) -> LLMResponse:
        """단일 primary 모델 호출 (하위 호환)."""
        model_id = self.config.model_ids[0]
        return await self._chat_one(
            prompt,
            model_id=model_id,
            role=role,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    async def _chat_one(
        self,
        prompt: str,
        *,
        model_id: str,
        role: ModelRole,
        system: str | None,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        return await self._client.chat(
            prompt,
            role=role,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            model_id=model_id,
        )

    async def run_with_parser(
        self,
        prompt: str,
        parse_fn: Callable[[dict[str, Any], str | None, str], dict[str, Any]],
        *,
        role: ModelRole = ModelRole.VISION,
        system: str | None = None,
        hint_icd: str | None = None,
        exam_type: str = "fundus",
        max_tokens: int = 1024,
        temperature: float = 0.4,
        telemetry_cb: Callable[[LLMResponse | None], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        """LLM 호출 + 파싱 + (선택) consensus → EyeAnalyzer 가 쓰는 raw dict.

        반환 키: raw_analysis, model_used, parsed (병합된 구조화 필드),
        vision_mode, per_model (consensus 시).
        """
        cfg = self.config

        async def _one(model_id: str) -> tuple[str, dict[str, Any], str]:
            resp = await self._chat_one(
                prompt,
                model_id=model_id,
                role=role,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            if telemetry_cb:
                await telemetry_cb(resp)
            raw = {"raw_analysis": resp.content, "model_used": resp.model_used}
            parsed = parse_fn(raw, hint_icd, exam_type)
            parsed["model_used"] = resp.model_used
            return model_id, parsed, resp.content

        if not cfg.is_consensus:
            mid, parsed, content = await _one(cfg.model_ids[0])
            return {
                "raw_analysis": content,
                "model_used": parsed.get("model_used", mid),
                "parsed": parsed,
                "vision_mode": "single",
                "per_model": [],
            }

        results = await asyncio.gather(
            *[_one(mid) for mid in cfg.model_ids],
            return_exceptions=True,
        )
        ok: list[tuple[str, dict[str, Any], str]] = []
        for item in results:
            if isinstance(item, Exception):
                log.warning("VISION 모델 호출 실패: %s", item)
                continue
            ok.append(item)

        if not ok:
            raise RuntimeError("모든 VISION 모델 호출 실패")

        parsed_list = [p for _, p, _ in ok]
        merged = merge_consensus(
            parsed_list,
            model_ids=tuple(mid for mid, _, _ in ok),
            min_agree=cfg.consensus_min_agree,
        )
        combined_raw = "\n---\n".join(
            f"[{_short_model_name(mid)}]\n{txt[:400]}" for mid, _, txt in ok
        )
        return {
            "raw_analysis": combined_raw,
            "model_used": merged["model_used"],
            "parsed": merged,
            "vision_mode": "consensus",
            "per_model": [
                {"model_id": mid, **p} for mid, p, _ in ok
            ],
        }


__all__ = [
    "VisionRoutingConfig",
    "VisionRouter",
    "load_vision_config",
    "merge_consensus",
]
