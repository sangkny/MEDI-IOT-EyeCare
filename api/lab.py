"""Fundus Lab — 안저 업로드 테스트 UI·API (다중 이미지 포맷)."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse

from auth.policy import policy_require
from schemas.integrated_diagnosis import (
    ComprehensiveDiagnosisResponse,
    DiagnosisExplainResponse,
)
from services.fundus_image_formats import (
    normalize_for_cnn,
    validate_fundus_upload,
)
from services.integrated_diagnosis import run_integrated_explain

log = logging.getLogger("api.lab")
router = APIRouter()

_LAB_HTML = Path(__file__).resolve().parent.parent / "static" / "fundus-lab" / "index.html"


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

    from api.diagnosis import _explanation_to_response

    resp = _explanation_to_response(
        explanation,
        hospitals,
        devices if comprehensive else None,
    )
    if hasattr(resp, "model_dump"):
        d = resp.model_dump()
        d["input_format"] = fmt_label
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
    "/fundus/comprehensive",
    response_model=ComprehensiveDiagnosisResponse,
    summary="Fundus Lab — comprehensive (multipart)",
)
async def lab_fundus_comprehensive(
    file: UploadFile = File(...),
    lang: str = Form("ko"),
    patient_id: str | None = Form(None),
    lat: float | None = Form(37.5665),
    lng: float | None = Form(126.9780),
    _: dict = LAB_AUTH,
):
    return await _run_lab_analysis(
        file, lang=lang, patient_id=patient_id, lat=lat, lng=lng, comprehensive=True
    )


@router.get("/fundus/formats", summary="지원 이미지 포맷 목록")
async def fundus_formats() -> dict:
    from services.fundus_image_formats import ALLOWED_EXTENSIONS, ALLOWED_MIME_TYPES

    return {
        "extensions": sorted(ALLOWED_EXTENSIONS),
        "mime_types": sorted(ALLOWED_MIME_TYPES),
        "max_mb": 20,
        "ui_path": "/api/v1/lab/fundus",
    }
