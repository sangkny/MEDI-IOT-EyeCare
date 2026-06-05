"""DR + Glaucoma 통합 안저 분석."""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

from schemas.integrated_diagnosis import (
    ComprehensiveFundusResponse,
    DRComprehensiveSummary,
    GlaucomaResult,
    OverallAssessment,
)
from services.cdr_estimator import get_cdr_estimator
from services.diagnosis_pipeline import apply_four_agent_glaucoma_decision
from services.glaucoma_cnn import (
    get_glaucoma_backend,
    get_glaucoma_model_path,
    predict_glaucoma_from_image_bytes,
    prediction_to_result,
)
from services.glaucoma_ontology import build_glaucoma_ontology_payload
from services.gradcam import GradCAMService, GradCAMVisualizer
from services.integrated_diagnosis import run_integrated_explain

log = logging.getLogger("services.comprehensive_fundus")

_URGENCY_RANK = {"none": 0, "routine": 1, "immediate": 2}


async def _run_glaucoma_pipeline(
    image_bytes: bytes,
    *,
    patient_id: str | None,
    eye: str | None,
    include_heatmap: bool,
) -> tuple[GlaucomaResult, dict | None]:
    pred = await predict_glaucoma_from_image_bytes(image_bytes)
    model_used = f"cnn({get_glaucoma_backend().model_label()})"
    estimator = get_cdr_estimator()
    cdr = await estimator.estimate(np.zeros((1, 1, 3), dtype=np.uint8), pred.probability)
    cdr_dict = cdr.to_dict()

    draft = prediction_to_result(
        pred,
        model_used=model_used,
        ontology_passed=True,
        decision_mode="pending",
        cup_disc_ratio=cdr_dict,
    )
    ontology_payload = build_glaucoma_ontology_payload(
        pred,
        model_used=model_used,
        icd10_code=draft.icd10_code,
        referral_urgency=draft.referral_urgency,
        eye=eye,
        cup_disc_ratio=cdr_dict,
    )
    onto, audit, mode = await apply_four_agent_glaucoma_decision(
        probability=pred.probability,
        confidence=pred.confidence,
        label=pred.label,
        glaucoma_grade=pred.glaucoma_grade,
        patient_id=patient_id,
        ontology_payload=ontology_payload,
    )

    heatmap_data: dict | None = None
    if include_heatmap:
        try:
            svc = GradCAMService()
            heatmap_data = await svc.generate_glaucoma_heatmap(
                image_bytes,
                str(get_glaucoma_model_path()),
                pred.probability,
                glaucoma_grade=pred.glaucoma_grade,
                eye_side=eye or "unknown",
            )
        except Exception as exc:
            log.exception("comprehensive glaucoma heatmap failed")
            heatmap_data = {"heatmap_error": str(exc)[:500], "image_base64": ""}

    result = prediction_to_result(
        pred,
        model_used=model_used,
        ontology_passed=onto,
        decision_mode=mode,
        audit_trail=audit,
        cup_disc_ratio=cdr_dict,
        heatmap=heatmap_data,
        decision=audit.get("decision"),
    )
    return result, heatmap_data


def _dr_summary_from_explain(
    explain_dict: dict[str, Any],
) -> DRComprehensiveSummary:
    audit = explain_dict.get("audit_trail") or {}
    return DRComprehensiveSummary(
        grade=int(explain_dict.get("dr_grade", 0)),  # type: ignore[call-arg]
        confidence=float(explain_dict.get("confidence", 0)),
        icd10_code=str(explain_dict.get("icd10_code", "")),
        severity=str(explain_dict.get("severity", "")),
        decision=audit.get("decision") or explain_dict.get("decision"),
        ontology_passed=bool(explain_dict.get("ontology_passed", False)),
        decision_mode=str(explain_dict.get("decision_mode", "legacy")),
        model_used=str(explain_dict.get("model_used", "")),
        audit_trail=audit,
    )


def _build_overall_assessment(
    dr: DRComprehensiveSummary,
    glaucoma: GlaucomaResult | None,
    *,
    lang: str = "ko",
) -> OverallAssessment:
    findings: list[str] = []
    primary = "none"
    urgency = "none"

    if lang == "ko":
        if dr.grade == 0:
            findings.append(f"DR grade 0 (정상)")
        else:
            findings.append(f"DR grade {dr.grade} ({dr.severity})")
    else:
        findings.append(f"DR grade {dr.grade} ({dr.severity})")

    if glaucoma is not None:
        cdr_val = None
        if glaucoma.cup_disc_ratio is not None:
            cdr_val = glaucoma.cup_disc_ratio.value
        if glaucoma.label == "glaucoma" or glaucoma.probability >= 0.5:
            if lang == "ko":
                cdr_note = f" (CDR {cdr_val:.3f})" if cdr_val else ""
                if glaucoma.risk_level == "HIGH":
                    findings.append(f"녹내장 고위험{cdr_note}")
                else:
                    findings.append(f"녹내장 의심{cdr_note}")
            else:
                findings.append(
                    f"Glaucoma suspect (p={glaucoma.probability:.3f})"
                )
            if glaucoma.probability >= dr.confidence or dr.grade <= 1:
                primary = "glaucoma"
        urgency = glaucoma.referral_urgency

    if dr.grade >= 2 and primary == "none":
        primary = "diabetic_retinopathy"
        urgency = "urgent" if dr.grade >= 3 else "routine"

    dr_urg = "routine" if dr.grade >= 1 else "none"
    if dr.grade >= 3:
        dr_urg = "immediate"
    for u in (urgency, dr_urg):
        if _URGENCY_RANK.get(u, 0) > _URGENCY_RANK.get(urgency, 0):
            urgency = u

    if lang == "ko":
        if urgency == "immediate":
            recommendation = "안과 전문의 즉시 의뢰"
        elif urgency == "routine":
            recommendation = "정기 안과 검진 및 추적 관찰 권장"
        else:
            recommendation = "특이 소견 없음 — 정기 검진 유지"
    else:
        recommendation = (
            "Immediate ophthalmology referral"
            if urgency == "immediate"
            else "Routine follow-up recommended"
        )

    return OverallAssessment(
        referral_urgency=urgency,
        primary_concern=primary,
        findings=findings,
        recommendation=recommendation,
    )


async def run_comprehensive_fundus(
    image_bytes: bytes,
    *,
    lang: str = "ko",
    patient_id: str | None = None,
    location: tuple[float, float] | None = None,
    eye: str | None = None,
    include_heatmap: bool = True,
    tasks: list[str] | None = None,
) -> ComprehensiveFundusResponse:
    """DR + Glaucoma 동시 분석."""
    active = tasks or ["dr", "glaucoma"]
    run_dr = "dr" in active
    run_glu = "glaucoma" in active

    explain_dict: dict[str, Any] = {}
    dr_heatmap: dict | None = None

    if run_dr:
        explanation, hospitals, devices = await run_integrated_explain(
            image_bytes,
            patient_lang=lang,
            patient_id=patient_id,
            location=location,
            include_devices=True,
        )
        from api.diagnosis import _apply_four_agent, _explanation_to_response

        onto, audit, mode = await _apply_four_agent(explanation, patient_id)
        resp = _explanation_to_response(
            explanation,
            hospitals,
            devices,
            ontology_passed=onto,
            audit_trail=audit,
            decision_mode=mode,
        )
        explain_dict = resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)

        if include_heatmap:
            try:
                dr_heatmap = await GradCAMVisualizer().generate_annotated(
                    image_bytes,
                    int(explain_dict.get("dr_grade", 0)),
                    eye_side=eye or "unknown",
                    lang=lang,
                )
            except Exception as exc:
                log.exception("comprehensive DR heatmap failed")
                dr_heatmap = {"heatmap_error": str(exc)[:500], "image_base64": ""}
    else:
        explain_dict = {"dr_grade": 0, "confidence": 0, "icd10_code": "", "severity": "normal"}

    glaucoma_result: GlaucomaResult | None = None
    glaucoma_heatmap: dict | None = None
    if run_glu:
        glaucoma_result, glaucoma_heatmap = await _run_glaucoma_pipeline(
            image_bytes,
            patient_id=patient_id,
            eye=eye,
            include_heatmap=include_heatmap,
        )

    dr_summary = _dr_summary_from_explain(explain_dict)
    overall = _build_overall_assessment(dr_summary, glaucoma_result, lang=lang)

    heatmaps: dict[str, Any] = {}
    if dr_heatmap:
        heatmaps["dr"] = dr_heatmap
    if glaucoma_heatmap:
        heatmaps["glaucoma"] = glaucoma_heatmap

    return ComprehensiveFundusResponse(
        dr=dr_summary,
        glaucoma=glaucoma_result,
        heatmap=heatmaps,
        overall_assessment=overall,
        active_tasks=active,
        input_format=explain_dict.get("input_format"),
        nearby_hospitals=explain_dict.get("nearby_hospitals") or [],
        device_recommendations=explain_dict.get("device_recommendations") or [],
    )
