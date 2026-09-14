"""Unit tests for MVP-02 result contract + clinical QC v1."""
from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

from services.clinical_image_qc import inference_allowed, run_clinical_image_qc
from services.mvp_result_contract import SCHEMA_VERSION, build_mvp_result_from_comprehensive


def _jpeg_bytes(arr: np.ndarray, quality: int = 90) -> bytes:
    img = Image.fromarray(arr.astype(np.uint8), mode="RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def _usable_fundus(size: int = 512) -> bytes:
    """Synthetic circular fundus-like image with texture (not solid)."""
    yy, xx = np.mgrid[0:size, 0:size]
    cy = cx = size // 2
    r = size * 0.42
    mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= r**2
    rgb = np.zeros((size, size, 3), dtype=np.uint8)
    # textured reddish fundus interior
    noise = (np.random.default_rng(0).random((size, size)) * 40).astype(np.uint8)
    rgb[..., 0] = np.where(mask, 120 + noise, 0)
    rgb[..., 1] = np.where(mask, 40 + noise // 2, 0)
    rgb[..., 2] = np.where(mask, 30 + noise // 3, 0)
    # vessel-like lines for sharpness
    rgb[size // 2 - 2 : size // 2 + 2, size // 5 : 4 * size // 5] = (200, 80, 60)
    rgb[size // 5 : 4 * size // 5, size // 2 - 2 : size // 2 + 2] = (180, 70, 50)
    return _jpeg_bytes(rgb)


def _blurred(size: int = 512) -> bytes:
    from PIL import Image, ImageFilter

    img = Image.open(io.BytesIO(_usable_fundus(size))).convert("RGB")
    for _ in range(8):
        img = img.filter(ImageFilter.GaussianBlur(radius=12))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _underexposed(size: int = 512) -> bytes:
    rgb = np.zeros((size, size, 3), dtype=np.uint8)
    rgb[80:400, 80:400] = (8, 5, 4)
    return _jpeg_bytes(rgb)


def _overexposed(size: int = 512) -> bytes:
    rgb = np.full((size, size, 3), 252, dtype=np.uint8)
    return _jpeg_bytes(rgb)


def test_pass_contract():
    payload = {
        "dr": {"dr_grade": 0, "confidence": 0.92, "audit_trail": {"decision": "APPROVE", "reason": "ok"}},
        "glaucoma": {"glaucoma_grade": 0, "probability": 0.1, "confidence": 0.9, "audit_trail": {"decision": "APPROVE"}},
        "amd": {},
        "myopia": {},
        "screening": {"findings": []},
        "overall_assessment": {"referral_urgency": "routine"},
        "heatmap": {},
    }
    out = build_mvp_result_from_comprehensive(
        payload, eye="R", trace_id="t1", image_id="img-1", include_heatmap=False
    )
    assert out["schema_version"] == SCHEMA_VERSION == "mvp02.v1"
    assert out["clinical_mode"] == "CLINICAL"
    assert out["decision"] == "PASS"
    assert out["trace_id"] == "t1"
    assert out["image_id"] == "img-1"
    assert out["preprocessing_version"]
    assert out["xai_status"] == "XAI_NOT_REQUESTED"
    assert out["gate"]["multi"] == "no_verified_below_gate_min"


def test_revise_contract_blocks_as_attention():
    payload = {
        "dr": {
            "dr_grade": 2,
            "confidence": 0.5,
            "audit_trail": {"decision": "REVISE", "reason": "below_gate_min"},
        },
        "glaucoma": {},
        "amd": {},
        "myopia": {},
        "screening": {},
        "overall_assessment": {"referral_urgency": "moderate"},
        "heatmap": {"dr": "data:image/png;base64,xxx"},
    }
    out = build_mvp_result_from_comprehensive(payload, eye="L", include_heatmap=True)
    assert out["decision"] == "REVISE"
    assert out["reason"] == "below_gate_min"
    assert out["risk_flag"] == "attention"
    assert out["xai_status"] == "XAI_AVAILABLE"


def test_qc_usable_pass_or_review():
    qc = run_clinical_image_qc(_usable_fundus())
    assert qc["qc_status"] in {"PASS", "REVIEW"}
    assert inference_allowed(qc, review_policy="allow")


def test_qc_blur_fail_or_review():
    qc = run_clinical_image_qc(_blurred())
    assert qc["qc_status"] in {"FAIL", "REVIEW"}
    assert "blur" in " ".join(qc["qc_reasons"])


def test_qc_underexposed():
    qc = run_clinical_image_qc(_underexposed())
    assert qc["qc_status"] in {"FAIL", "REVIEW"}
    joined = " ".join(qc["qc_reasons"])
    assert any(
        k in joined
        for k in ("underexposure", "fov", "artifact", "solid", "crop", "border")
    )


def test_qc_overexposed():
    qc = run_clinical_image_qc(_overexposed())
    assert qc["qc_status"] in {"FAIL", "REVIEW"}
    joined = " ".join(qc["qc_reasons"])
    assert any(k in joined for k in ("overexposure", "artifact", "solid"))


def test_qc_fail_blocks_inference():
    qc = run_clinical_image_qc(b"")
    assert qc["qc_status"] == "FAIL"
    assert inference_allowed(qc, review_policy="allow") is False


def test_qc_review_policy():
    qc = {"qc_status": "REVIEW"}
    assert inference_allowed(qc, review_policy="block") is False
    assert inference_allowed(qc, review_policy="allow") is True
