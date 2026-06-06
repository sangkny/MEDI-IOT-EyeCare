"""Fundus Lab — 안저 업로드 테스트 UI·API (다중 이미지 포맷)."""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from auth.policy import policy_require
from schemas.integrated_diagnosis import (
    AMDResult,
    ComprehensiveFundusResponse,
    DiagnosisExplainResponse,
    GlaucomaResult,
    MyopiaResult,
    ScreeningResult,
)
from services.fundus_image_formats import (
    normalize_for_cnn,
    validate_fundus_upload,
)
from services.integrated_diagnosis import run_integrated_explain
from services.fundus_video import (
    MAX_VIDEO_BYTES,
    aggregate_dr_predictions,
    extract_jpeg_frames_from_video,
    validate_fundus_video_upload,
)
from services.inference_router import predict_dr_from_image_bytes
from services.retinal_cnn import dr_prediction_to_parsed

log = logging.getLogger("api.lab")
router = APIRouter()

_LAB_HTML = Path(__file__).resolve().parent.parent / "static" / "fundus-lab" / "index.html"
_VIDEO_DR_HTML = Path(__file__).resolve().parent.parent / "static" / "video-dr-lab" / "index.html"


def _lab_open() -> bool:
    return os.getenv("MEDI_FUNDUS_LAB_OPEN", "1") in {"1", "true", "TRUE"}


async def _noop_lab_auth() -> dict:
    return {}


LAB_AUTH = (
    Depends(_noop_lab_auth)
    if _lab_open()
    else Depends(policy_require("medi-iot", "ai_analyze"))
)


async def _read_and_validate(file: UploadFile) -> tuple[bytes, str]:
    content = await file.read()
    try:
        mime, fmt = validate_fundus_upload(
            content,
            filename=file.filename,
            content_type=file.content_type,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc
    normalized = normalize_for_cnn(content)
    return normalized, f"{fmt} ({mime})"


async def _run_lab_analysis(
    file: UploadFile,
    *,
    lang: str,
    patient_id: str | None,
    lat: float | None,
    lng: float | None,
    comprehensive: bool,
    include_heatmap: bool = False,
    eye_side: str = "unknown",
):
    image_bytes, fmt_label = await _read_and_validate(file)
    loc = None
    if lat is not None and lng is not None:
        loc = (lat, lng)

    try:
        explanation, hospitals, devices = await run_integrated_explain(
            image_bytes,
            patient_lang=lang,
            patient_id=patient_id,
            location=loc,
            include_devices=comprehensive,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"CNN model unavailable: {exc}",
        ) from exc
    except Exception as exc:
        log.error("lab analysis failed: %s", exc)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc)[:200],
        ) from exc

    from api.diagnosis import _apply_four_agent, _explanation_to_response

    onto, audit, mode = await _apply_four_agent(explanation, patient_id)
    resp = _explanation_to_response(
        explanation,
        hospitals,
        devices if comprehensive else None,
        ontology_passed=onto,
        audit_trail=audit,
        decision_mode=mode,
    )
    if hasattr(resp, "model_dump"):
        d = resp.model_dump()
        d["input_format"] = fmt_label
        if include_heatmap:
            try:
                from services.gradcam import GradCAMVisualizer

                ann = await GradCAMVisualizer().generate_annotated(
                    image_bytes,
                    int(d.get("dr_grade", 0)),
                    eye_side=eye_side,
                    lang=lang,
                )
                d.update(ann)
            except Exception as exc:
                log.exception("lab heatmap failed")
                d["heatmap_base64"] = ""
                d["heatmap_error"] = str(exc)[:500]
                d["gradcam_version"] = None
                d["attention_score"] = None
                d["hotspot_regions"] = []
        return d
    return resp


@router.get(
    "/fundus",
    response_class=HTMLResponse,
    summary="Fundus Lab 웹 UI",
    include_in_schema=True,
)
async def fundus_lab_page() -> FileResponse:
    """브라우저에서 안저 이미지 업로드·CNN+LLM 테스트."""
    if not _LAB_HTML.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="fundus-lab UI not found")
    return FileResponse(_LAB_HTML, media_type="text/html; charset=utf-8")


@router.post(
    "/fundus/explain",
    summary="Fundus Lab — explain (multipart)",
)
async def lab_fundus_explain(
    file: UploadFile = File(..., description="JPEG/PNG/TIFF/BMP/WebP/HEIC"),
    lang: str = Form("ko"),
    patient_id: str | None = Form(None),
    lat: float | None = Form(None),
    lng: float | None = Form(None),
    _: dict = LAB_AUTH,
):
    return await _run_lab_analysis(
        file, lang=lang, patient_id=patient_id, lat=lat, lng=lng, comprehensive=False
    )


@router.post(
    "/fundus/glaucoma",
    response_model=GlaucomaResult,
    summary="녹내장 단독 분석 (retinal_glaucoma_v2)",
)
async def lab_fundus_glaucoma(
    file: UploadFile = File(...),
    patient_id: str | None = Form(None),
    eye: str | None = Form(None),
    include_heatmap: bool = Form(True),
    _: dict = LAB_AUTH,
) -> GlaucomaResult:
    """EfficientNet-B4 + Focal Loss (v2, val AUC≈0.946). Gate min conf 기본 0.65."""
    image_bytes, _ = await _read_and_validate(file)
    try:
        import numpy as np

        from services.cdr_estimator import get_cdr_estimator
        from services.diagnosis_pipeline import apply_four_agent_glaucoma_decision
        from services.glaucoma_cnn import (
            get_glaucoma_backend,
            get_glaucoma_model_path,
            predict_glaucoma_from_image_bytes,
            prediction_to_result,
        )
        from services.glaucoma_ontology import build_glaucoma_ontology_payload
        from services.gradcam import GradCAMService

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
                log.exception("lab glaucoma heatmap failed")
                heatmap_data = {
                    "image_base64": "",
                    "resolution": "",
                    "lesion_annotations": [],
                    "hotspot_regions": [],
                    "heatmap_error": str(exc)[:500],
                }

        return prediction_to_result(
            pred,
            model_used=model_used,
            ontology_passed=onto,
            decision_mode=mode,
            audit_trail=audit,
            cup_disc_ratio=cdr_dict,
            heatmap=heatmap_data,
            decision=audit.get("decision"),
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Glaucoma model not found: {exc}",
        ) from exc
    except Exception as exc:
        log.exception("lab glaucoma failed")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc)[:200],
        ) from exc


@router.post(
    "/fundus/amd",
    response_model=AMDResult,
    summary="AMD 단독 분석 (retinal_amd_v1)",
)
async def lab_fundus_amd(
    file: UploadFile = File(...),
    patient_id: str | None = Form(None),
    eye: str | None = Form(None),
    include_heatmap: bool = Form(True),
    _: dict = LAB_AUTH,
) -> AMDResult:
    """EfficientNet-B4 + Focal Loss (amd_v1, val AUC≈0.9803). Gate min conf 기본 0.65."""
    image_bytes, _ = await _read_and_validate(file)
    try:
        from services.amd_cnn import (
            get_amd_backend,
            get_amd_model_path,
            predict_amd_from_image_bytes,
            prediction_to_result,
        )
        from services.amd_ontology import build_amd_ontology_payload
        from services.diagnosis_pipeline import apply_four_agent_amd_decision
        from services.gradcam import GradCAMService

        pred = await predict_amd_from_image_bytes(image_bytes)
        model_used = f"cnn({get_amd_backend().model_label()})"

        draft = prediction_to_result(
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
                log.exception("lab amd heatmap failed")
                heatmap_data = {
                    "image_base64": "",
                    "resolution": "",
                    "lesion_annotations": [],
                    "hotspot_regions": [],
                    "heatmap_error": str(exc)[:500],
                }

        return prediction_to_result(
            pred,
            model_used=model_used,
            ontology_passed=onto,
            decision_mode=mode,
            audit_trail=audit,
            heatmap=heatmap_data,
            decision=audit.get("decision"),
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AMD model not found: {exc}",
        ) from exc
    except Exception as exc:
        log.exception("lab amd failed")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc)[:200],
        ) from exc


@router.post(
    "/fundus/myopia",
    response_model=MyopiaResult,
    summary="근시 단독 분석 (Phase 3 skeleton)",
)
async def lab_fundus_myopia(
    file: UploadFile = File(...),
    _: dict = LAB_AUTH,
) -> MyopiaResult:
    """Phase 3: PALM/ODIR 근시 subset 기반 myopia head."""
    await _read_and_validate(file)
    raise HTTPException(
        status.HTTP_501_NOT_IMPLEMENTED,
        detail="Myopia model not deployed yet (Phase 3 — PALM training planned)",
    )


@router.post(
    "/fundus/screening",
    response_model=ScreeningResult,
    summary="전체 안과 스크리닝 (Phase 4 skeleton)",
)
async def lab_fundus_screening(
    file: UploadFile = File(...),
    tasks: str = Form("dr,glaucoma,amd,myopia", description="쉼표 구분 태스크"),
    _: dict = LAB_AUTH,
) -> ScreeningResult:
    """다질환 통합 스크리닝 — RFMiD/ODIR 멀티헤드 (모델 준비 중)."""
    await _read_and_validate(file)
    raise HTTPException(
        status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"Multidisease screening not deployed yet (tasks={tasks})",
    )


@router.post(
    "/fundus/comprehensive",
    response_model=ComprehensiveFundusResponse,
    summary="Fundus Lab — DR + Glaucoma 통합 분석",
)
async def lab_fundus_comprehensive(
    file: UploadFile = File(...),
    lang: str = Form("ko"),
    patient_id: str | None = Form(None),
    lat: float | None = Form(37.5665),
    lng: float | None = Form(126.9780),
    include_heatmap: bool = Form(True),
    eye: str | None = Form(None, description="left | right (alias eye_side)"),
    eye_side: str = Form("unknown", description="left | right | unknown"),
    tasks: str = Form("dr,glaucoma,amd", description="쉼표 구분: dr,glaucoma,amd"),
    _: dict = LAB_AUTH,
) -> ComprehensiveFundusResponse:
    """DR + Glaucoma + AMD 동시 분석 · overall_assessment 종합 판정."""
    image_bytes, fmt_label = await _read_and_validate(file)
    loc = None
    if lat is not None and lng is not None:
        loc = (lat, lng)
    active = [t.strip().lower() for t in tasks.split(",") if t.strip()]
    eye_eff = eye or eye_side
    try:
        from services.comprehensive_fundus import run_comprehensive_fundus

        result = await run_comprehensive_fundus(
            image_bytes,
            lang=lang,
            patient_id=patient_id,
            location=loc,
            eye=eye_eff,
            include_heatmap=include_heatmap,
            tasks=active,
        )
        if fmt_label and result.input_format is None:
            return result.model_copy(update={"input_format": fmt_label})
        return result
    except FileNotFoundError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Model unavailable: {exc}",
        ) from exc
    except Exception as exc:
        log.exception("comprehensive fundus failed")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc)[:200],
        ) from exc


@router.post(
    "/fundus/attention",
    summary="RETFound attention map (multipart, v8+)",
)
async def lab_fundus_attention(
    file: UploadFile = File(...),
    _: dict = LAB_AUTH,
) -> dict:
    """ViT attention 기반 병변 위치 히트맵 (skeleton → v8 ONNX 연동 후 정밀화)."""
    image_bytes, _ = await _read_and_validate(file)
    try:
        from services.retfound_attention import RETFoundAttentionExtractor

        return await asyncio.to_thread(
            RETFoundAttentionExtractor().extract, image_bytes
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc)[:200],
        ) from exc
    except Exception as exc:
        log.exception("attention extract failed")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc)[:200],
        ) from exc


@router.get(
    "/fundus/attention/{image_id}",
    summary="RETFound attention by cached image_id (planned)",
)
async def lab_fundus_attention_by_id(image_id: str, _: dict = LAB_AUTH) -> dict:
    raise HTTPException(
        status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"image_id cache not implemented yet: {image_id}",
    )


@router.get("/fundus/formats", summary="지원 이미지 포맷 목록")
async def fundus_formats() -> dict:
    from services.fundus_image_formats import ALLOWED_EXTENSIONS, ALLOWED_MIME_TYPES

    return {
        "extensions": sorted(ALLOWED_EXTENSIONS),
        "mime_types": sorted(ALLOWED_MIME_TYPES),
        "max_mb": 20,
        "ui_path": "/api/v1/lab/fundus",
        "video_dr_ui_path": "/api/v1/lab/video-dr",
    }


class VideoFrameDrOut(BaseModel):
    """프레임별 DR(CNN) 요약."""

    frame_index: int = Field(..., ge=0)
    dr_grade: int = Field(..., ge=0, le=4)
    confidence: float = Field(..., ge=0.0, le=1.0)
    icd10_code: str | None = None
    severity: str | None = None


class VideoDrAnalyzeResponse(BaseModel):
    """영상 업로드 → 샘플 프레임 DR 집계."""

    video_format: str
    n_frames_sampled: int
    max_frames_requested: int
    aggregate: dict
    per_frame: list[VideoFrameDrOut]
    note: str = (
        "집계는 샘플 프레임의 **최대 DR 등급(가장 심각)** 기준입니다. "
        "임상 판단은 의료진 검진으로 대체할 수 없습니다."
    )


@router.get(
    "/video-dr",
    response_class=HTMLResponse,
    summary="안저 영상 DR Lab UI",
    include_in_schema=True,
)
async def video_dr_lab_page() -> FileResponse:
    """브라우저에서 mp4/webm 업로드 → 프레임 샘플 CNN DR."""
    if not _VIDEO_DR_HTML.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="video-dr-lab UI not found")
    return FileResponse(_VIDEO_DR_HTML, media_type="text/html; charset=utf-8")


@router.post(
    "/video-dr/analyze",
    response_model=VideoDrAnalyzeResponse,
    summary="안저 영상(mp4/webm) — 프레임 샘플 DR(CNN) 집계",
)
async def lab_video_dr_analyze(
    file: UploadFile = File(..., description="mp4 또는 webm"),
    max_frames: int = Form(8, ge=1, le=24, description="추출·추론할 최대 프레임 수"),
    _: dict = LAB_AUTH,
) -> VideoDrAnalyzeResponse:
    raw = await file.read()
    if len(raw) > MAX_VIDEO_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"video too large (max {MAX_VIDEO_BYTES // (1024 * 1024)}MB)",
        )
    try:
        fmt = validate_fundus_video_upload(
            raw,
            filename=file.filename,
            content_type=file.content_type,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc

    try:
        jpeg_frames = extract_jpeg_frames_from_video(
            raw,
            max_frames=max_frames,
            target_fps=0.25,
            fmt_hint=fmt,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    if not jpeg_frames:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="프레임을 추출하지 못했습니다. 코덱·손상 파일 여부를 확인하세요.",
        )

    sem = asyncio.Semaphore(3)

    async def _infer_one(jpeg: bytes) -> object:
        b = normalize_for_cnn(jpeg)
        async with sem:
            return await predict_dr_from_image_bytes(b)

    try:
        preds = await asyncio.gather(*[_infer_one(j) for j in jpeg_frames])
    except FileNotFoundError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CNN 모델(.onnx 등)을 찾을 수 없습니다. 컨테이너에 모델을 두거나 requirements-ml 환경을 사용하세요.",
        ) from exc
    except Exception as exc:
        log.exception("video DR batch failed")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc)[:240],
        ) from exc

    pred_list = list(preds)
    agg = aggregate_dr_predictions(pred_list)
    agg_parsed = dr_prediction_to_parsed(agg)

    per_frame: list[VideoFrameDrOut] = []
    for i, p in enumerate(pred_list):
        parsed = dr_prediction_to_parsed(p)
        per_frame.append(
            VideoFrameDrOut(
                frame_index=i,
                dr_grade=p.dr_grade,
                confidence=float(p.confidence),
                icd10_code=parsed.get("icd10_code"),
                severity=parsed.get("severity"),
            )
        )

    return VideoDrAnalyzeResponse(
        video_format=fmt,
        n_frames_sampled=len(jpeg_frames),
        max_frames_requested=max_frames,
        aggregate=dict(agg_parsed),
        per_frame=per_frame,
    )
