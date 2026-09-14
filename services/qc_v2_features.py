"""QC-v2 feature metrics — FEATURE PREVIEW only.

Does NOT alter qc-v1.0-provisional PASS/REVIEW/FAIL thresholds.
Optic disc / macula scores are heuristic EXPERIMENTAL proxies, not clinical detectors.
"""
from __future__ import annotations

from typing import Any

import numpy as np

QC_FEATURE_VERSION = "qc-v2-feature-preview"

FEATURE_STATUS = {
    "optic_disc_visibility": "EXPERIMENTAL",
    "macula_visibility": "EXPERIMENTAL",
    "fundus_circular_field": "FEATURE-ONLY",
    "glare_reflection": "FEATURE-ONLY",
    "eyelash_eyelid_artifact": "EXPERIMENTAL",
    "motion_blur_proxy": "FEATURE-ONLY",
    "color_channel_abnormality": "FEATURE-ONLY",
    "partial_framing": "FEATURE-ONLY",
}


def compute_qc_v2_features(
    rgb: np.ndarray,
    gray: np.ndarray,
    *,
    base_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return feature scores only — never used for gate decisions."""
    h, w = gray.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    cy, cx = h / 2.0, w / 2.0
    r = min(h, w) * 0.42
    circle = ((xx - cx) ** 2 + (yy - cy) ** 2) <= (r**2)
    outside = ~circle

    fg = float((gray > 20).mean()) if gray.size else 0.0
    in_cov = float((gray[circle] > 20).mean()) if circle.any() else 0.0
    out_dark = float((gray[outside] < 15).mean()) if outside.any() else 0.0
    circularity = round(in_cov * out_dark, 4)

    # Glare: bright specular-like pixels
    glare = float((gray > 245).mean())
    # Color channel abnormality: R/G ratio extreme or near-gray
    rch = rgb[..., 0].astype(np.float64)
    gch = rgb[..., 1].astype(np.float64)
    bch = rgb[..., 2].astype(np.float64)
    rg = float((rch.mean() + 1e-6) / (gch.mean() + 1e-6))
    channel_std = float(np.std([rch.mean(), gch.mean(), bch.mean()]))

    # Motion-like blur proxy: ratio of high-freq energy (already have laplacian in base)
    lap = float((base_metrics or {}).get("laplacian_var") or 0.0)
    motion_proxy = round(1.0 / (1.0 + lap / 50.0), 4)

    # Partial framing: coverage concentrated on one side
    left = float(gray[:, : w // 2].mean())
    right = float(gray[:, w // 2 :].mean())
    top = float(gray[: h // 2, :].mean())
    bot = float(gray[h // 2 :, :].mean())
    asymmetry = round(abs(left - right) / 255.0 + abs(top - bot) / 255.0, 4)

    # Experimental disc/macula proxies: bright central vs temporal dark — NOT a detector
    # Disc often brighter; macula often darker — crude quadrant stats only
    q = gray[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4]
    disc_proxy = round(float(q.max()) / 255.0, 4) if q.size else 0.0
    macula_proxy = round(1.0 - float(np.percentile(q, 20)) / 255.0, 4) if q.size else 0.0

    # Eyelash/eyelid experimental: dark linear-ish top/bottom bands
    band = max(2, h // 12)
    top_band = float((gray[:band, :] < 30).mean())
    bot_band = float((gray[-band:, :] < 30).mean())
    eyelash_proxy = round(max(top_band, bot_band), 4)

    return {
        "qc_feature_version": QC_FEATURE_VERSION,
        "gate_influence": "NONE",
        "note": "FEATURE PREVIEW — does not change qc-v1 PASS/REVIEW/FAIL",
        "feature_status": FEATURE_STATUS,
        "scores": {
            "disc_visibility_score": disc_proxy,
            "macula_visibility_score": macula_proxy,
            "fundus_coverage": round(fg, 4),
            "circular_field_score": circularity,
            "glare_score": round(glare, 4),
            "artifact_score": round(eyelash_proxy + glare, 4),
            "eyelash_eyelid_score": eyelash_proxy,
            "motion_blur_proxy": motion_proxy,
            "color_rg_ratio": round(rg, 4),
            "color_channel_std": round(channel_std, 4),
            "framing_asymmetry": asymmetry,
        },
        "backlog": [
            "trained_optic_disc_detector",
            "trained_macula_detector",
            "validated_artifact_classifier",
        ],
    }
