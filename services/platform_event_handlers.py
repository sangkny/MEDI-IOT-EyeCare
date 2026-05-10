"""Week 6 — 다른 플랫폼이 발행한 Redis 이벤트 수신 (MEDI-IOT 측)."""
from __future__ import annotations

import logging
from typing import Any

from events.constants import EVENT_CONTRACT_APPROVED

log = logging.getLogger("services.platform_event_handlers")


async def medi_incoming_dispatch(event_type: str, data: dict[str, Any]) -> None:
    """CoOps `contract.approved` → 장비 발주 등 후속 단계 트리거(플레이스홀더)."""
    if event_type != EVENT_CONTRACT_APPROVED:
        return
    cn = str(data.get("contract_number", "") or "")
    appr = str(data.get("approval_id", "") or "")
    log.info(
        "[MEDI-IOT] 계약 승인 이벤트 수신 → 장비 발주 연동(예정) contract=%s approval=%s",
        cn,
        appr,
    )
