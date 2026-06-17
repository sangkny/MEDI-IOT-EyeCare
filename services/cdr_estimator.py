"""Cup-to-Disc Ratio (CDR) 추정 — Protocol 기반, segmentation 교체 가능."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

import numpy as np

if TYPE_CHECKING:
    import torch

CDRCategory = Literal["normal", "suspect", "glaucoma"]
EstimationMethod = Literal["probability_based", "segmentation_based"]


@dataclass(frozen=True)
class CDRResult:
    cdr_value: float
    cdr_category: CDRCategory
    estimation_method: EstimationMethod
    confidence_interval: tuple[float, float]
    clinical_note: str

    def to_dict(self) -> dict:
        return {
            "value": round(self.cdr_value, 3),
            "category": self.cdr_category,
            "method": self.estimation_method,
            "confidence_interval": [
                round(self.confidence_interval[0], 3),
                round(self.confidence_interval[1], 3),
            ],
            "clinical_note": self.clinical_note,
        }


def _category_from_cdr(cdr: float) -> CDRCategory:
    if cdr > 0.75:
        return "glaucoma"
    if cdr >= 0.65:
        return "suspect"
    return "normal"


def _clinical_note(cdr: float, category: CDRCategory) -> str:
    if category == "glaucoma":
        return (
            f"CDR {cdr:.2f} — 녹내장 범위(>0.75). "
            "시신경유두 정밀 검사 및 안압 측정 권장."
        )
    if category == "suspect":
        return (
            f"CDR {cdr:.2f} — 녹내장 의심 범위(0.65~0.75). "
            "정밀 검사 및 추적 관찰 권장."
        )
    return f"CDR {cdr:.2f} — 정상 범위(<0.65)."


def cdr_from_disc_cup_mask(mask: np.ndarray) -> float:
    """픽셀 마스크(0=배경, 1=disc, 2=cup)에서 CDR 계산."""
    cup_area = float((mask == 2).sum())
    disc_area = float(((mask == 1) | (mask == 2)).sum())
    if disc_area < 1.0:
        return 0.0
    return float(np.clip(cup_area / disc_area, 0.0, 1.0))


def cdr_from_seg_logits(logits: "torch.Tensor") -> "torch.Tensor":
    """세그멘테이션 logits (N,3,H,W) → 배치 CDR."""
    import torch

    pred = logits.argmax(dim=1)
    cup = (pred == 2).sum(dim=(1, 2)).float()
    disc = ((pred == 1) | (pred == 2)).sum(dim=(1, 2)).float()
    return (cup / disc.clamp(min=1.0)).clamp(0.0, 1.0)


def estimate_cdr_from_probability(probability: float) -> CDRResult:
    """probability → CDR 근사 매핑 (임상 근사값)."""
    p = max(0.0, min(1.0, float(probability)))
    if p >= 0.8:
        low, high, center = 0.75, 0.85, 0.80
        span = high - low
        t = min(1.0, (p - 0.8) / 0.2)
        cdr = low + span * (0.4 + 0.6 * t)
    elif p >= 0.6:
        low, high = 0.65, 0.75
        t = (p - 0.6) / 0.2
        cdr = low + (high - low) * t
    else:
        low, high = 0.45, 0.65
        t = p / 0.6 if p < 0.6 else 1.0
        cdr = low + (high - low) * t

    cdr = float(np.clip(cdr, 0.0, 1.0))
    half_band = 0.04 if p >= 0.8 else 0.03
    ci = (
        float(np.clip(cdr - half_band, 0.0, 1.0)),
        float(np.clip(cdr + half_band, 0.0, 1.0)),
    )
    cat = _category_from_cdr(cdr)
    return CDRResult(
        cdr_value=cdr,
        cdr_category=cat,
        estimation_method="probability_based",
        confidence_interval=ci,
        clinical_note=_clinical_note(cdr, cat),
    )


@runtime_checkable
class CDREstimator(Protocol):
    async def estimate(
        self, image: np.ndarray, probability: float
    ) -> CDRResult: ...


class ProbabilityBasedCDR:
    """CNN probability 기반 CDR 근사 (즉시 사용 가능)."""

    async def estimate(
        self, image: np.ndarray, probability: float
    ) -> CDRResult:
        del image
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, estimate_cdr_from_probability, probability
        )


class SegmentationBasedCDR:
    """optic disc/cup segmentation → 실제 CDR (향후 구현)."""

    async def estimate(
        self, image: np.ndarray, probability: float
    ) -> CDRResult:
        del image, probability
        raise NotImplementedError(
            "SegmentationBasedCDR is not yet implemented; "
            "use ProbabilityBasedCDR."
        )


_default_estimator: ProbabilityBasedCDR | None = None


def get_cdr_estimator() -> CDREstimator:
    global _default_estimator
    if _default_estimator is None:
        _default_estimator = ProbabilityBasedCDR()
    return _default_estimator
