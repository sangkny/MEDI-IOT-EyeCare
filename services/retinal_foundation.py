"""RETFound 등 Foundation 모델 로더 (D R4-ML D4, 선택).

환경:
    MEDI_USE_FOUNDATION_MODEL=retfound

참고: `RETFound_MAE` — https://github.com/rmaphoh/RETFound_MAE

로컬에 가중치가 없으면 import/로드 실패 시 **경고만** 출력하고 ``None`` 반환.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger("services.retinal_foundation")

RETFOUND_REPO = "https://github.com/rmaphoh/RETFound_MAE"
DEFAULT_CHECKPOINT = Path("models/retfound_vit_large.pth")


def foundation_model_requested() -> str | None:
    raw = (os.getenv("MEDI_USE_FOUNDATION_MODEL") or "").strip().lower()
    return raw or None


def load_retfound_encoder(
    checkpoint: Path | None = None,
    *,
    device: str = "cpu",
) -> Any | None:
    """RETFound ViT encoder lazy load. 실패 시 None + warning."""
    ckpt = checkpoint or Path(os.getenv("MEDI_RETFOUND_CHECKPOINT", str(DEFAULT_CHECKPOINT)))
    if not ckpt.is_file():
        log.warning(
            "RETFound checkpoint not found at %s — skip foundation model. "
            "Clone %s and place weights under models/.",
            ckpt,
            RETFOUND_REPO,
        )
        return None
    try:
        import torch
    except ImportError:
        log.warning("torch not installed — RETFound skipped")
        return None

    try:
        state = torch.load(ckpt, map_location=device, weights_only=False)
    except TypeError:
        state = torch.load(ckpt, map_location=device)
    except Exception as exc:
        log.warning("RETFound load failed: %s", exc)
        return None

    log.info("RETFound checkpoint loaded from %s (encoder hook only — fine-tune separately)", ckpt)
    return state


def maybe_warn_foundation_skip() -> None:
    """요청됐으나 체크포인트 없을 때 한 줄 안내."""
    name = foundation_model_requested()
    if not name:
        return
    if name == "retfound":
        load_retfound_encoder()
    else:
        log.warning("Unknown MEDI_USE_FOUNDATION_MODEL=%r — ignored", name)


__all__ = [
    "foundation_model_requested",
    "load_retfound_encoder",
    "maybe_warn_foundation_skip",
    "RETFOUND_REPO",
]
