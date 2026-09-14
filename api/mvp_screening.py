"""MVP-01 clinical screening endpoint — thin adapter over comprehensive_fundus."""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status

from services.mvp_result_contract import SCHEMA_VERSION, build_mvp_result_from_comprehensive

log = logging.getLogger("api.mvp_screening")
router = APIRouter(tags=["mvp"])


def _basic_qc(image_bytes: bytes, filename: str | None) -> dict:
    checks: list[str] = []
    if not image_bytes:
        return {"status": "failed", "checks": ["empty"], "detail": "empty image"}
    checks.append("nonempty")
    if len(image_bytes) < 100:
        return {"status": "failed", "checks": checks + ["too_small"], "detail": "image too small"}
    checks.append("min_bytes")
    try:
        from services.fundus_image_formats import validate_fundus_upload

        validate_fundus_upload(image_bytes, filename=filename)
        checks.append("format")
    except ValueError as exc:
        return {"status": "failed", "checks": checks, "detail": str(exc)}
    # Clinical blur/FOV/macula QC: NOT IMPLEMENTED — format gate only
    checks.append("clinical_qc_not_implemented")
    return {"status": "passed_format_only", "checks": checks}


@router.post("/mvp/clinical-screening")
async def mvp_clinical_screening(
    file: UploadFile = File(...),
    eye: str = Form("R"),
    lang: str = Form("ko"),
    patient_id: str | None = Form(None),
    include_heatmap: bool = Form(False),
    mode: str = Query("fast", description="fast=v10c | precise=specialists"),
    preprocess: str = Query("none", description="serving preprocess; v10c meta default none"),
) -> dict:
    """Versioned clinical result for eyecare-platform consumers (MVP-01)."""
    image_bytes = await file.read()
    qc = _basic_qc(image_bytes, file.filename)
    if qc.get("status") == "failed":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "qc_failed", "qc": qc, "schema_version": SCHEMA_VERSION},
        )

    trace_id = str(uuid.uuid4())
    try:
        from services.comprehensive_fundus import run_comprehensive_fundus

        result = await run_comprehensive_fundus(
            image_bytes,
            lang=lang,
            patient_id=patient_id,
            eye=eye,
            include_heatmap=include_heatmap,
            tasks=["dr", "glaucoma", "amd", "myopia", "screening"],
            mode=mode,
            preprocess=preprocess,
        )
        payload = result.model_dump() if hasattr(result, "model_dump") else dict(result)
    except FileNotFoundError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "model_unavailable", "message": str(exc), "trace_id": trace_id},
        ) from exc
    except Exception as exc:
        log.exception("mvp clinical screening failed")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "inference_unavailable", "message": str(exc)[:200], "trace_id": trace_id},
        ) from exc

    return build_mvp_result_from_comprehensive(
        payload, eye=eye, trace_id=trace_id, qc=qc
    )
