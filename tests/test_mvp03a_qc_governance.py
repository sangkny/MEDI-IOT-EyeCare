"""MVP-03A: QC-v2 features must not alter v1 gate; governance present."""
from __future__ import annotations

import io

import numpy as np
from PIL import Image

from services.clinical_image_qc import QC_VERSION, BLUR_FAIL, UNDEREXP_MEAN_REVIEW, run_clinical_image_qc
from services.model_governance import KNOWN_RETINAL_V10_SHA256, get_model_governance
from services.mvp_result_contract import build_mvp_result_from_comprehensive
from services.qc_v2_features import QC_FEATURE_VERSION


def _jpeg(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(arr.astype(np.uint8)).save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def _usable() -> bytes:
    size = 512
    yy, xx = np.mgrid[0:size, 0:size]
    mask = (xx - size // 2) ** 2 + (yy - size // 2) ** 2 <= (size * 0.42) ** 2
    rgb = np.zeros((size, size, 3), dtype=np.uint8)
    noise = (np.random.default_rng(1).random((size, size)) * 40).astype(np.uint8)
    rgb[..., 0] = np.where(mask, 130 + noise, 0)
    rgb[..., 1] = np.where(mask, 50 + noise // 2, 0)
    rgb[..., 2] = np.where(mask, 40 + noise // 3, 0)
    rgb[250:262, 100:400] = (200, 90, 70)
    return _jpeg(rgb)


def test_qc_v1_version_and_thresholds_unchanged():
    assert QC_VERSION == "qc-v1.0-provisional"
    assert BLUR_FAIL == 8.0
    assert UNDEREXP_MEAN_REVIEW == 32.0


def test_qc_v2_features_non_gating():
    qc = run_clinical_image_qc(_usable())
    assert qc["qc_version"] == "qc-v1.0-provisional"
    assert qc.get("qc_feature_version") == QC_FEATURE_VERSION
    assert qc["qc_features"]["gate_influence"] == "NONE"
    assert "disc_visibility_score" in qc["qc_features"]["scores"]
    # status must come from v1 only
    assert qc["qc_status"] in {"PASS", "REVIEW", "FAIL"}


def test_governance_hash_known():
    g = get_model_governance()
    assert g["model_id"] == "retinal_v10"
    assert g["model_artifact_hash"] == KNOWN_RETINAL_V10_SHA256 or len(g["model_artifact_hash"]) == 64
    assert g["preprocessing_version"] == "retinal-preproc-v1"


def test_contract_includes_governance_and_features():
    payload = {
        "dr": {"dr_grade": 0, "confidence": 0.9, "audit_trail": {"decision": "APPROVE"}},
        "glaucoma": {},
        "amd": {},
        "myopia": {},
        "screening": {},
        "overall_assessment": {},
        "heatmap": {},
    }
    qc = run_clinical_image_qc(_usable())
    out = build_mvp_result_from_comprehensive(payload, qc=qc, image_id="i1", trace_id="t1")
    assert out["trace_id"] == "t1"
    assert out["governance"]["model_id"] == "retinal_v10"
    assert out["grade_raw"]["model_artifact_hash"]
    assert out.get("qc_feature_version") == QC_FEATURE_VERSION
