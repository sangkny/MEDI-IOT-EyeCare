"""
파일명: gl_ensemble.py
목적: v10c GL 불확실 구간에서 glaucoma_v2 재검증 앙상블
히스토리:
  2026-06-12 - 최초 작성 (D+B GL 개선 계획)
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Protocol

from services.glaucoma_cnn import GlaucomaOnnxBackend, GlaucomaPrediction


class GlaucomaV2Predictor(Protocol):
    """glaucoma_v2 ONNX 백엔드 (predict_sync)."""

    def predict_sync(self, image_bytes: bytes) -> GlaucomaPrediction: ...


def _ensemble_enabled() -> bool:
    flag = (os.getenv("MEDI_GL_ENSEMBLE_ENABLED") or "1").strip().lower()
    return flag not in ("0", "false", "off", "no")


class GlaucomaEnsemble:
    """v10c GL 확률 + glaucoma_v2 전문 모델 가중 앙상블."""

    UNCERTAIN_LOW = 0.30
    UNCERTAIN_HIGH = 0.70
    W_V10C = 0.35
    W_V2 = 0.65

    async def predict(
        self,
        *,
        image_bytes: bytes,
        v10c_prob: float,
        glaucoma_v2_model: GlaucomaV2Predictor | GlaucomaOnnxBackend,
    ) -> dict[str, Any]:
        """
        v10c GL 확률 기반 앙상블 예측.

        Returns:
            probability, method, v10c_prob, v2_prob, ensemble_weight
        """
        p = max(0.0, min(1.0, float(v10c_prob)))

        if not _ensemble_enabled():
            return {
                "probability": p,
                "method": "v10c_only_disabled",
                "v10c_prob": p,
                "v2_prob": None,
                "ensemble_weight": None,
            }

        if p < self.UNCERTAIN_LOW:
            return {
                "probability": p,
                "method": "v10c_certain_normal",
                "v10c_prob": p,
                "v2_prob": None,
                "ensemble_weight": None,
            }

        if p > self.UNCERTAIN_HIGH:
            return {
                "probability": p,
                "method": "v10c_certain_abnormal",
                "v10c_prob": p,
                "v2_prob": None,
                "ensemble_weight": None,
            }

        loop = asyncio.get_running_loop()
        v2_pred: GlaucomaPrediction = await loop.run_in_executor(
            None, glaucoma_v2_model.predict_sync, image_bytes
        )
        v2_prob = float(v2_pred.probability)
        ensemble_prob = p * self.W_V10C + v2_prob * self.W_V2

        return {
            "probability": round(ensemble_prob, 6),
            "method": "ensemble_v10c_v2",
            "v10c_prob": p,
            "v2_prob": v2_prob,
            "ensemble_weight": {"v10c": self.W_V10C, "v2": self.W_V2},
        }
