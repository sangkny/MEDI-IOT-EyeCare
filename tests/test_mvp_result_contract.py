"""Unit tests for MVP-01 result contract mapping (no ONNX required)."""
from __future__ import annotations

from services.mvp_result_contract import build_mvp_result_from_comprehensive


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
    out = build_mvp_result_from_comprehensive(payload, eye="R", trace_id="t1")
    assert out["schema_version"] == "mvp01.v1"
    assert out["clinical_mode"] == "CLINICAL"
    assert out["decision"] == "PASS"
    assert out["trace_id"] == "t1"
    assert out["risk_flag"] == "normal"
    assert out["gate"]["dr_min"] == 0.80
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
    out = build_mvp_result_from_comprehensive(payload, eye="L")
    assert out["decision"] == "REVISE"
    assert out["reason"] == "below_gate_min"
    assert out["risk_flag"] == "attention"
    assert out["xai"] is not None
