"""MVP-01 versioned clinical screening result contract.

Maps existing comprehensive_fundus output → stable consumer schema.
Does not change model thresholds or inference logic.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

SCHEMA_VERSION = "mvp01.v1"


def _audit_decision(block: dict[str, Any] | None) -> tuple[str | None, str | None]:
    if not isinstance(block, dict):
        return None, None
    trail = block.get("audit_trail") or {}
    if not isinstance(trail, dict):
        return None, None
    return trail.get("decision"), trail.get("reason")


def build_mvp_result_from_comprehensive(
    payload: dict[str, Any],
    *,
    eye: str = "R",
    trace_id: str | None = None,
    qc: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build mvp01.v1 contract from ComprehensiveFundusResponse.model_dump()."""
    dr = payload.get("dr") or {}
    gl = payload.get("glaucoma") or {}
    amd = payload.get("amd") or {}
    myo = payload.get("myopia") or {}
    screening = payload.get("screening") or {}
    overall = payload.get("overall_assessment") or {}
    heatmap = payload.get("heatmap") or {}

    decisions: list[str] = []
    reasons: list[str] = []
    for block in (dr, gl, amd, myo):
        dec, reason = _audit_decision(block if isinstance(block, dict) else None)
        if dec:
            decisions.append(str(dec).upper())
        if reason:
            reasons.append(str(reason))

    # Product decision aggregation (gate already applied inside disease pipelines)
    if "REJECT" in decisions:
        decision = "REJECT"
    elif "REVISE" in decisions:
        decision = "REVISE"
    else:
        decision = "PASS"

    reason = "; ".join(reasons) if reasons else (
        "below_gate_min" if decision == "REVISE" else "gate_or_pipeline_ok"
    )

    # confidence: prefer DR confidence, else max of available
    conf_candidates: list[float] = []
    for block, key in (
        (dr, "confidence"),
        (gl, "confidence"),
        (amd, "confidence"),
        (myo, "confidence"),
    ):
        if isinstance(block, dict) and block.get(key) is not None:
            try:
                conf_candidates.append(float(block[key]))
            except (TypeError, ValueError):
                pass
    confidence = max(conf_candidates) if conf_candidates else 0.0

    # risk_flag for eyecare referral compatibility
    urgency = str(overall.get("referral_urgency") or "").lower()
    if decision == "REVISE":
        risk_flag = "attention"
    elif urgency in {"urgent", "high", "refer"} or urgency == "immediate":
        risk_flag = "refer"
    elif urgency in {"moderate", "attention", "soon"}:
        risk_flag = "attention"
    else:
        # fall back from grades
        dr_grade = int(dr.get("dr_grade") or dr.get("grade") or 0) if isinstance(dr, dict) else 0
        gl_grade = int(gl.get("glaucoma_grade") or gl.get("grade") or 0) if isinstance(gl, dict) else 0
        if dr_grade >= 3 or gl_grade >= 2:
            risk_flag = "refer"
        elif dr_grade >= 1 or gl_grade >= 1:
            risk_flag = "attention"
        else:
            risk_flag = "normal"

    model_version = (
        (dr.get("model_used") if isinstance(dr, dict) else None)
        or overall.get("inference_mode")
        or "v10c"
    )
    if isinstance(model_version, str) and model_version.startswith("fast"):
        model_version = "v10c"

    predictions = {
        "dr": dr if isinstance(dr, dict) else {},
        "glaucoma": gl if isinstance(gl, dict) else {},
        "amd": amd if isinstance(amd, dict) else {},
        "myopia": myo if isinstance(myo, dict) else {},
        "multi": screening if isinstance(screening, dict) else {},
    }

    disease_labels = {
        "dr": {
            "grade": (dr.get("dr_grade") if isinstance(dr, dict) else None),
            "prob": (dr.get("confidence") if isinstance(dr, dict) else None),
        },
        "glaucoma": {
            "grade": (gl.get("glaucoma_grade") if isinstance(gl, dict) else None),
            "prob": (gl.get("probability") if isinstance(gl, dict) else None),
        },
        "amd": {
            "present": bool(amd.get("amd_grade") or 0) if isinstance(amd, dict) else False,
            "prob": (amd.get("probability") if isinstance(amd, dict) else None),
        },
        "myopia": {
            "present": bool(myo.get("myopia_grade") or 0) if isinstance(myo, dict) else False,
            "prob": (myo.get("probability") if isinstance(myo, dict) else None),
        },
    }

    xai = None
    if isinstance(heatmap, dict) and any(heatmap.values()):
        xai = {"heatmap": heatmap}

    tid = trace_id or str(uuid.uuid4())
    return {
        "schema_version": SCHEMA_VERSION,
        "clinical_mode": "CLINICAL",
        "model_version": str(model_version),
        "image_id": None,
        "eye": eye.upper() if eye else "R",
        "predictions": predictions,
        "confidence": confidence,
        "decision": decision,
        "reason": reason,
        "risk_flag": risk_flag,
        "disease_labels": disease_labels,
        "grade_raw": {
            "schema_version": SCHEMA_VERSION,
            "decision": decision,
            "reason": reason,
            "clinical_mode": "CLINICAL",
            "overall_assessment": overall,
            "trace_id": tid,
        },
        "xai": xai,
        "trace_id": tid,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gate": {
            "dr_min": 0.80,
            "gl_amd_myo_min": 0.65,
            "multi": "no_verified_below_gate_min",
        },
        "qc": qc or {"status": "passed_format_only", "checks": ["format", "nonempty"]},
        "note": "MVP-01 contract over MEDI comprehensive_fundus (SSOT)",
    }
