"""Clinical Image QC v1 — engineering / provisional thresholds.

DATA BASIS: SYNTHETIC/SAMPLE fundus images (MVP-01/02 engineering).
THRESHOLD STATUS: PROVISIONAL — NOT clinically validated.

Optic disc / macula visibility: NOT IMPLEMENTED (QC-v2 backlog).
"""
from __future__ import annotations

import io
import logging
from typing import Any

import numpy as np

log = logging.getLogger("services.clinical_image_qc")

QC_VERSION = "qc-v1.0-provisional"

MIN_SIDE_FAIL = 128
MIN_SIDE_REVIEW = 224
MIN_BYTES = 200
BLUR_FAIL = 8.0
BLUR_REVIEW = 25.0
UNDEREXP_MEAN_FAIL = 25.0
# Provisional: typical dark fundus samples sit ~40–55 mean; REVIEW only for darker than ~32
UNDEREXP_MEAN_REVIEW = 32.0
OVEREXP_MEAN_FAIL = 235.0
OVEREXP_MEAN_REVIEW = 220.0
OVEREXP_PCT_FAIL = 0.50
FOV_COVERAGE_FAIL = 0.12
FOV_COVERAGE_REVIEW = 0.25
BORDER_BLACK_FRAC_FAIL = 0.85
SOLID_COLOR_STD_FAIL = 8.0


def _decode_rgb(image_bytes: bytes) -> tuple[np.ndarray | None, str | None]:
    if not image_bytes:
        return None, "empty"
    if len(image_bytes) < MIN_BYTES:
        return None, "too_small_bytes"
    try:
        import cv2

        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if bgr is not None:
            return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), None
    except Exception:  # noqa: BLE001
        pass
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        return np.asarray(img, dtype=np.uint8), None
    except Exception as exc:  # noqa: BLE001
        log.warning("qc decode failed: %s", type(exc).__name__)
        return None, "undecodable"


def _laplacian_variance(gray: np.ndarray) -> float:
    try:
        import cv2

        lap = cv2.Laplacian(gray, cv2.CV_64F)
        return float(lap.var())
    except Exception:  # noqa: BLE001
        # 4-neighbor Laplacian variance (numpy fallback)
        g = gray.astype(np.float64)
        lap = (
            -g[:-2, 1:-1]
            - g[1:-1, :-2]
            + 4 * g[1:-1, 1:-1]
            - g[1:-1, 2:]
            - g[2:, 1:-1]
        )
        return float(lap.var())


def _to_gray(rgb: np.ndarray) -> np.ndarray:
    try:
        import cv2

        return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    except Exception:  # noqa: BLE001
        return (
            0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
        ).astype(np.uint8)


def _resize_max_side(rgb: np.ndarray, max_side: int = 512) -> np.ndarray:
    h, w = rgb.shape[:2]
    m = max(h, w)
    if m <= max_side:
        return rgb
    scale = max_side / float(m)
    nh, nw = int(h * scale), int(w * scale)
    try:
        import cv2

        return cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA)
    except Exception:  # noqa: BLE001
        from PIL import Image

        img = Image.fromarray(rgb)
        img = img.resize((nw, nh), Image.Resampling.BILINEAR)
        return np.asarray(img, dtype=np.uint8)


def run_clinical_image_qc(image_bytes: bytes, *, filename: str | None = None) -> dict[str, Any]:
    reasons: list[str] = []
    metrics: dict[str, Any] = {
        "filename": filename,
        "threshold_status": "PROVISIONAL",
        "data_basis": "SYNTHETIC/SAMPLE",
        "disc_macula_visibility": "NOT_IMPLEMENTED_QC_V2",
    }

    rgb, err = _decode_rgb(image_bytes)
    if rgb is None:
        return {
            "qc_version": QC_VERSION,
            "qc_status": "FAIL",
            "qc_reasons": [err or "undecodable"],
            "qc_metrics": metrics,
            "status": "failed",
            "checks": [err or "undecodable"],
        }

    h, w = int(rgb.shape[0]), int(rgb.shape[1])
    metrics["height"] = h
    metrics["width"] = w
    metrics["bytes"] = len(image_bytes)

    status = "PASS"

    def escalate(level: str, reason: str) -> None:
        nonlocal status
        reasons.append(reason)
        order = {"PASS": 0, "REVIEW": 1, "FAIL": 2}
        if order[level] > order[status]:
            status = level

    side = min(h, w)
    if side < MIN_SIDE_FAIL:
        escalate("FAIL", "resolution_too_low")
    elif side < MIN_SIDE_REVIEW:
        escalate("REVIEW", "resolution_marginal")

    small = _resize_max_side(rgb, 512)
    gray = _to_gray(small)
    sharp = _laplacian_variance(gray)
    metrics["laplacian_var"] = round(sharp, 3)
    if sharp < BLUR_FAIL:
        escalate("FAIL", "blur_severe")
    elif sharp < BLUR_REVIEW:
        escalate("REVIEW", "blur_marginal")

    mean_b = float(gray.mean())
    metrics["brightness_mean"] = round(mean_b, 2)
    bright_frac = float((gray > 250).mean())
    metrics["overexp_pixel_frac"] = round(bright_frac, 4)
    if mean_b < UNDEREXP_MEAN_FAIL:
        escalate("FAIL", "underexposure_severe")
    elif mean_b < UNDEREXP_MEAN_REVIEW:
        escalate("REVIEW", "underexposure_marginal")
    if mean_b > OVEREXP_MEAN_FAIL or bright_frac > OVEREXP_PCT_FAIL:
        escalate("FAIL", "overexposure_severe")
    elif mean_b > OVEREXP_MEAN_REVIEW:
        escalate("REVIEW", "overexposure_marginal")

    fg = float((gray > 20).mean())
    metrics["fov_coverage"] = round(fg, 4)
    if fg < FOV_COVERAGE_FAIL:
        escalate("FAIL", "fov_inadequate")
    elif fg < FOV_COVERAGE_REVIEW:
        escalate("REVIEW", "fov_marginal")

    bh, bw = gray.shape
    edge_w = max(2, min(bh, bw) // 20)
    edges = np.concatenate(
        [
            gray[:edge_w, :].ravel(),
            gray[-edge_w:, :].ravel(),
            gray[:, :edge_w].ravel(),
            gray[:, -edge_w:].ravel(),
        ]
    )
    black_edge = float((edges < 15).mean())
    metrics["border_black_frac"] = round(black_edge, 4)
    if black_edge > BORDER_BLACK_FRAC_FAIL and fg < 0.5:
        escalate("FAIL", "severe_crop_or_border")

    std = float(gray.std())
    metrics["gray_std"] = round(std, 2)
    if std < SOLID_COLOR_STD_FAIL:
        escalate("FAIL", "gross_artifact_or_solid")

    # QC-v2 feature preview — MUST NOT influence status/reasons above
    try:
        from services.qc_v2_features import QC_FEATURE_VERSION, compute_qc_v2_features

        features = compute_qc_v2_features(rgb, gray, base_metrics=metrics)
    except Exception as exc:  # noqa: BLE001
        log.warning("qc_v2 features skipped: %s", type(exc).__name__)
        features = {
            "qc_feature_version": "qc-v2-feature-preview",
            "gate_influence": "NONE",
            "error": "feature_compute_failed",
        }

    return {
        "qc_version": QC_VERSION,
        "qc_feature_version": features.get("qc_feature_version"),
        "qc_status": status,
        "qc_reasons": reasons,
        "qc_metrics": metrics,
        "qc_features": features,
        "status": "failed" if status == "FAIL" else ("review" if status == "REVIEW" else "passed"),
        "checks": reasons or ["ok"],
        "detail": ";".join(reasons) if reasons else "ok",
    }


def inference_allowed(qc: dict[str, Any], *, review_policy: str = "block") -> bool:
    st = str(qc.get("qc_status") or "").upper()
    if st == "FAIL":
        return False
    if st == "REVIEW":
        return review_policy.strip().lower() in {"allow", "pass", "continue"}
    return True
