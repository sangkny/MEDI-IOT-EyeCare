"""DR + Glaucoma + AMD 통합 안저 분석."""

from __future__ import annotations



import logging

from typing import Any



import numpy as np



from schemas.integrated_diagnosis import (

    AMDResult,

    ComprehensiveFundusResponse,

    DRComprehensiveSummary,

    GlaucomaResult,

    MyopiaResult,

    OverallAssessment,

    ScreeningResult,

)

from services.amd_cnn import (

    get_amd_backend,

    get_amd_model_path,

    predict_amd_from_image_bytes,

    prediction_to_result as amd_prediction_to_result,

)

from services.amd_ontology import build_amd_ontology_payload

from services.cdr_estimator import get_cdr_estimator

from services.diagnosis_pipeline import (

    apply_four_agent_amd_decision,

    apply_four_agent_glaucoma_decision,

    apply_four_agent_myopia_decision,

)

from services.glaucoma_cnn import (

    get_glaucoma_backend,

    get_glaucoma_model_path,

    predict_glaucoma_from_image_bytes,

    prediction_to_result,

)

from services.glaucoma_ontology import build_glaucoma_ontology_payload

from services.myopia_cnn import (

    get_myopia_backend,

    get_myopia_model_path,

    predict_myopia_from_image_bytes,

    prediction_to_result as myopia_prediction_to_result,

)

from services.myopia_ontology import build_myopia_ontology_payload

from services.glaucoma_cnn import GlaucomaPrediction
from services.amd_cnn import AMDPrediction
from services.myopia_cnn import MyopiaPrediction
from services.multidisease_cnn import (
    DISEASE_MAP,
    MultidiseasePrediction,
    prediction_to_screening_result,
    screen_fundus_from_image_bytes,
)
from services.v10_cnn import get_v10_backend, is_v10_available, predict_v10_from_image_bytes

from services.gradcam import GradCAMService, GradCAMVisualizer

from services.integrated_diagnosis import run_integrated_explain



log = logging.getLogger("services.comprehensive_fundus")



_URGENCY_RANK = {"none": 0, "routine": 1, "urgent": 2, "immediate": 3}





async def _run_glaucoma_pipeline(

    image_bytes: bytes,

    *,

    patient_id: str | None,

    eye: str | None,

    include_heatmap: bool,

    pred: GlaucomaPrediction | None = None,

) -> tuple[GlaucomaResult, dict | None]:

    if pred is None:

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





async def _run_amd_pipeline(

    image_bytes: bytes,

    *,

    patient_id: str | None,

    eye: str | None,

    include_heatmap: bool,

    pred: AMDPrediction | None = None,

) -> tuple[AMDResult, dict | None]:

    if pred is None:

        pred = await predict_amd_from_image_bytes(image_bytes)

    model_used = f"cnn({get_amd_backend().model_label()})"



    draft = amd_prediction_to_result(

        pred,

        model_used=model_used,

        ontology_passed=True,

        decision_mode="pending",

    )

    ontology_payload = build_amd_ontology_payload(

        pred,

        model_used=model_used,

        icd10_code=draft.icd10_code,

        referral_urgency=draft.referral_urgency,

        eye=eye,

    )

    onto, audit, mode = await apply_four_agent_amd_decision(

        probability=pred.probability,

        confidence=pred.confidence,

        label=pred.label,

        amd_grade=pred.amd_grade,

        patient_id=patient_id,

        ontology_payload=ontology_payload,

    )



    heatmap_data: dict | None = None

    if include_heatmap:

        try:

            svc = GradCAMService()

            heatmap_data = await svc.generate_amd_heatmap(

                image_bytes,

                str(get_amd_model_path()),

                pred.probability,

                amd_grade=pred.amd_grade,

                eye_side=eye or "unknown",

            )

        except Exception as exc:

            log.exception("comprehensive amd heatmap failed")

            heatmap_data = {"heatmap_error": str(exc)[:500], "image_base64": ""}



    result = amd_prediction_to_result(

        pred,

        model_used=model_used,

        ontology_passed=onto,

        decision_mode=mode,

        audit_trail=audit,

        heatmap=heatmap_data,

        decision=audit.get("decision"),

    )

    return result, heatmap_data





async def _run_myopia_pipeline(

    image_bytes: bytes,

    *,

    patient_id: str | None,

    eye: str | None,

    include_heatmap: bool,

    pred: MyopiaPrediction | None = None,

) -> tuple[MyopiaResult, dict | None]:

    if pred is None:

        pred = await predict_myopia_from_image_bytes(image_bytes)

    model_used = f"cnn({get_myopia_backend().model_label()})"



    draft = myopia_prediction_to_result(

        pred,

        model_used=model_used,

        ontology_passed=True,

        decision_mode="pending",

    )

    ontology_payload = build_myopia_ontology_payload(

        pred,

        model_used=model_used,

        icd10_code=draft.icd10_code,

        referral_urgency=draft.referral_urgency,

        eye=eye,

    )

    onto, audit, mode = await apply_four_agent_myopia_decision(

        probability=pred.probability,

        confidence=pred.confidence,

        label=pred.label,

        myopia_grade=pred.myopia_grade,

        patient_id=patient_id,

        ontology_payload=ontology_payload,

    )



    heatmap_data: dict | None = None

    if include_heatmap:

        try:

            svc = GradCAMService()

            heatmap_data = await svc.generate_myopia_heatmap(

                image_bytes,

                str(get_myopia_model_path()),

                pred.probability,

                myopia_grade=pred.myopia_grade,

                eye_side=eye or "unknown",

            )

        except Exception as exc:

            log.exception("comprehensive myopia heatmap failed")

            heatmap_data = {"heatmap_error": str(exc)[:500], "image_base64": ""}



    result = myopia_prediction_to_result(

        pred,

        model_used=model_used,

        ontology_passed=onto,

        decision_mode=mode,

        audit_trail=audit,

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

        decision=audit.get("decision") or explain_dict.get("decision") or "REVISE",

        ontology_passed=bool(explain_dict.get("ontology_passed", False)),

        decision_mode=str(explain_dict.get("decision_mode", "legacy")),

        model_used=str(explain_dict.get("model_used", "")),

        audit_trail=audit,

    )





def _task_urgency(urgency: str) -> int:

    return _URGENCY_RANK.get(urgency, 0)





def _pick_higher_urgency(current: str, candidate: str) -> str:

    if _task_urgency(candidate) > _task_urgency(current):

        return candidate

    return current


_STANDARD_CONCERNS = frozenset({"glaucoma", "amd", "myopia", "diabetic_retinopathy"})


def _format_concern_label(code: str, lang: str) -> str:
    if code in _STANDARD_CONCERNS:
        return code
    korean, _ = DISEASE_MAP.get(code, ("", ""))
    if lang == "ko" and korean:
        return f"{code} ({korean})"
    return code


def _resolve_primary_concern(concern_scores: dict[str, float], lang: str) -> str:
    if not concern_scores:
        return "none"
    ranked = sorted(concern_scores.items(), key=lambda x: x[1], reverse=True)
    top_code, top_score = ranked[0]
    if len(ranked) > 1:
        second_code, second_score = ranked[1]
        if second_score >= 0.5 and second_score >= top_score * 0.9:
            return f"{top_code} + {second_code}"
    return _format_concern_label(top_code, lang)





def _build_overall_assessment(

    dr: DRComprehensiveSummary,

    glaucoma: GlaucomaResult | None,

    amd: AMDResult | None = None,

    myopia: MyopiaResult | None = None,

    screening: ScreeningResult | None = None,

    *,

    lang: str = "ko",

) -> OverallAssessment:

    findings: list[str] = []

    primary = "none"

    urgency = "none"



    if lang == "ko":

        if dr.grade == 0:

            findings.append("DR grade 0 (정상)")

        else:

            findings.append(f"DR grade {dr.grade} ({dr.severity})")

    else:

        findings.append(f"DR grade {dr.grade} ({dr.severity})")



    concern_scores: dict[str, float] = {}



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

                findings.append(f"Glaucoma suspect (p={glaucoma.probability:.3f})")

            concern_scores["glaucoma"] = glaucoma.probability

        urgency = _pick_higher_urgency(urgency, glaucoma.referral_urgency)



    if amd is not None:

        if amd.label == "amd" or amd.probability >= 0.5:

            if lang == "ko":

                drusen = amd.drusen_type or "none"

                findings.append(

                    f"황반변성(AMD) 의심 (p={amd.probability:.2f}, drusen={drusen})"

                )

            else:

                findings.append(f"AMD suspect (p={amd.probability:.3f})")

            concern_scores["amd"] = amd.probability

        urgency = _pick_higher_urgency(urgency, amd.referral_urgency)



    if myopia is not None:

        if myopia.label == "myopia" or myopia.probability >= 0.5:

            if lang == "ko":

                axial = (

                    f", AL≈{myopia.axial_length_estimate:.1f}mm"

                    if myopia.axial_length_estimate

                    else ""

                )

                findings.append(

                    f"근시 의심 (p={myopia.probability:.2f}, grade={myopia.myopia_grade}{axial})"

                )

            else:

                findings.append(f"Myopia suspect (p={myopia.probability:.3f})")

            concern_scores["myopia"] = myopia.probability

        urgency = _pick_higher_urgency(urgency, myopia.referral_urgency)



    if screening is not None:

        if screening.findings:

            if lang == "ko":

                top = screening.top_findings or screening.findings[:3]

                for f in top:

                    name = f.korean_name or f.disease

                    findings.append(f"다질환: {name} (p={f.probability:.2f})")

                    concern_scores[f.disease] = f.probability

            else:

                for f in (screening.top_findings or screening.findings[:3]):

                    findings.append(f"Screening: {f.disease} p={f.probability:.3f}")

                    concern_scores[f.disease] = f.probability

        elif screening.normal and lang == "ko":

            findings.append("다질환 스크리닝: 특이 소견 없음")

        urgency = _pick_higher_urgency(urgency, screening.referral_urgency)



    if dr.grade >= 2:

        concern_scores["diabetic_retinopathy"] = dr.confidence



    dr_urg = "routine" if dr.grade >= 1 else "none"

    if dr.grade >= 3:

        dr_urg = "immediate"

    urgency = _pick_higher_urgency(urgency, dr_urg)



    if concern_scores:

        primary = _resolve_primary_concern(concern_scores, lang)

    elif dr.grade >= 2:

        primary = "diabetic_retinopathy"



    if lang == "ko":

        if urgency == "immediate":

            recommendation = "안과 전문의 즉시 의뢰 — 시력 위협 소견"

        elif urgency == "urgent":

            recommendation = "안과 전문의 조속 내원 권장"

        elif urgency == "routine":

            recommendation = "정기 안과 검진 및 추적 관찰 권장"

        else:

            recommendation = "특이 소견 없음 — 정기 검진 유지"

    else:

        recommendation = (

            "Immediate ophthalmology referral"

            if urgency in ("immediate", "urgent")

            else "Routine follow-up recommended"

        )



    return OverallAssessment(

        referral_urgency=urgency,

        primary_concern=primary,

        findings=findings,

        recommendation=recommendation,

    )





async def _run_comprehensive_v10(

    image_bytes: bytes,

    *,

    lang: str = "ko",

    patient_id: str | None = None,

    eye: str | None = None,

    include_heatmap: bool = True,

    tasks: list[str] | None = None,

) -> ComprehensiveFundusResponse:

    """v10 단일 ONNX — 5질환 동시 추론."""

    active = tasks or ["dr", "glaucoma", "amd", "myopia", "screening"]

    v10 = await predict_v10_from_image_bytes(image_bytes)

    model_used = f"cnn({get_v10_backend().model_label()})"



    dr_summary = DRComprehensiveSummary(

        grade=v10.dr.dr_grade,

        confidence=v10.dr.confidence,

        icd10_code=v10.dr.icd10_code,

        severity=v10.dr.severity,

        decision="APPROVE" if v10.dr.confidence >= 0.5 else "REVISE",

        ontology_passed=True,

        decision_mode="v10_cnn",

        model_used=model_used,

        audit_trail={"source": "v10_single_forward"},

    )



    glaucoma_result: GlaucomaResult | None = None

    glaucoma_heatmap: dict | None = None

    if "glaucoma" in active:

        glaucoma_result, glaucoma_heatmap = await _run_glaucoma_pipeline(

            image_bytes,

            patient_id=patient_id,

            eye=eye,

            include_heatmap=include_heatmap,

            pred=v10.glaucoma,

        )



    amd_result: AMDResult | None = None

    amd_heatmap: dict | None = None

    if "amd" in active:

        amd_result, amd_heatmap = await _run_amd_pipeline(

            image_bytes,

            patient_id=patient_id,

            eye=eye,

            include_heatmap=include_heatmap,

            pred=v10.amd,

        )



    myopia_result: MyopiaResult | None = None

    myopia_heatmap: dict | None = None

    if "myopia" in active:

        myopia_result, myopia_heatmap = await _run_myopia_pipeline(

            image_bytes,

            patient_id=patient_id,

            eye=eye,

            include_heatmap=include_heatmap,

            pred=v10.myopia,

        )



    screening_result: ScreeningResult | None = None

    if "screening" in active:

        screening_result = prediction_to_screening_result(

            v10.multidisease,

            model_used=model_used,

        )



    overall = _build_overall_assessment(

        dr_summary, glaucoma_result, amd_result, myopia_result, screening_result, lang=lang

    )



    heatmaps: dict[str, Any] = {}

    if glaucoma_heatmap:

        heatmaps["glaucoma"] = glaucoma_heatmap

    if amd_heatmap:

        heatmaps["amd"] = amd_heatmap

    if myopia_heatmap:

        heatmaps["myopia"] = myopia_heatmap



    return ComprehensiveFundusResponse(

        dr=dr_summary,

        glaucoma=glaucoma_result,

        amd=amd_result,

        myopia=myopia_result,

        screening=screening_result,

        heatmap=heatmaps,

        overall_assessment=overall,

        active_tasks=active,

        input_format="v10_onnx",

        nearby_hospitals=[],

        device_recommendations=[],

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

    """DR + Glaucoma + AMD + Myopia + 다질환 스크리닝 동시 분석."""

    active = tasks or ["dr", "glaucoma", "amd", "myopia", "screening"]



    if is_v10_available() and set(active) <= {"dr", "glaucoma", "amd", "myopia", "screening"}:

        return await _run_comprehensive_v10(

            image_bytes,

            lang=lang,

            patient_id=patient_id,

            eye=eye,

            include_heatmap=include_heatmap,

            tasks=active,

        )

    run_dr = "dr" in active

    run_glu = "glaucoma" in active

    run_amd = "amd" in active

    run_myopia = "myopia" in active

    run_screening = "screening" in active



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



    amd_result: AMDResult | None = None

    amd_heatmap: dict | None = None

    if run_amd:

        amd_result, amd_heatmap = await _run_amd_pipeline(

            image_bytes,

            patient_id=patient_id,

            eye=eye,

            include_heatmap=include_heatmap,

        )



    myopia_result: MyopiaResult | None = None

    myopia_heatmap: dict | None = None

    if run_myopia:

        myopia_result, myopia_heatmap = await _run_myopia_pipeline(

            image_bytes,

            patient_id=patient_id,

            eye=eye,

            include_heatmap=include_heatmap,

        )



    screening_result: ScreeningResult | None = None

    if run_screening:

        screening_result = await screen_fundus_from_image_bytes(

            image_bytes,

            eye=eye,

        )



    dr_summary = _dr_summary_from_explain(explain_dict)

    overall = _build_overall_assessment(

        dr_summary, glaucoma_result, amd_result, myopia_result, screening_result, lang=lang

    )



    heatmaps: dict[str, Any] = {}

    if dr_heatmap:

        heatmaps["dr"] = dr_heatmap

    if glaucoma_heatmap:

        heatmaps["glaucoma"] = glaucoma_heatmap

    if amd_heatmap:

        heatmaps["amd"] = amd_heatmap

    if myopia_heatmap:

        heatmaps["myopia"] = myopia_heatmap



    return ComprehensiveFundusResponse(

        dr=dr_summary,

        glaucoma=glaucoma_result,

        amd=amd_result,

        myopia=myopia_result,

        screening=screening_result,

        heatmap=heatmaps,

        overall_assessment=overall,

        active_tasks=active,

        input_format=explain_dict.get("input_format"),

        nearby_hospitals=explain_dict.get("nearby_hospitals") or [],

        device_recommendations=explain_dict.get("device_recommendations") or [],

    )

