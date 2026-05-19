"""FHIR R4 최소 export API (D R3 D4).

``Content-Type: application/fhir+json``

라우트 (prefix ``/clinical/fhir``):
    GET /Patient/{patient_id}
    GET /Observation/image/{image_id}
    GET /DiagnosticReport/{diagnosis_id}
    GET /Patient/{patient_id}/bundle
"""
from __future__ import annotations

import logging

from auth.dependencies import current_user_strict
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models.medical import Diagnosis, EyeExam, EyeImage, Patient
from services.fhir_export import (
    FHIR_JSON,
    diagnostic_report_from_diagnosis,
    observation_from_image,
    patient_bundle,
    patient_to_fhir,
)

log = logging.getLogger("api.fhir")
router = APIRouter()


def _fhir_response(resource: dict) -> JSONResponse:
    return JSONResponse(content=resource, media_type=FHIR_JSON)


@router.get(
    "/Patient/{patient_id}",
    summary="FHIR Patient export",
    responses={200: {"content": {FHIR_JSON: {}}}},
)
async def fhir_patient(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(current_user_strict),
) -> JSONResponse:
    patient = await db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="patient not found")
    return _fhir_response(patient_to_fhir(patient))


@router.get(
    "/Observation/image/{image_id}",
    summary="FHIR Observation (VISION image analysis)",
    responses={200: {"content": {FHIR_JSON: {}}}},
)
async def fhir_observation_image(
    image_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(current_user_strict),
) -> JSONResponse:
    image = await db.scalar(
        select(EyeImage).where(EyeImage.id == image_id)
    )
    if not image:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="image not found")
    patient = await db.get(Patient, image.patient_id)
    if not patient:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="patient not found")
    return _fhir_response(observation_from_image(image, patient))


@router.get(
    "/DiagnosticReport/{diagnosis_id}",
    summary="FHIR DiagnosticReport (AI diagnosis)",
    responses={200: {"content": {FHIR_JSON: {}}}},
)
async def fhir_diagnostic_report(
    diagnosis_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(current_user_strict),
) -> JSONResponse:
    diag = await db.scalar(
        select(Diagnosis)
        .where(Diagnosis.id == diagnosis_id)
        .options(selectinload(Diagnosis.exam))
    )
    if not diag or not diag.exam:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="diagnosis not found")
    patient = await db.get(Patient, diag.exam.patient_id)
    if not patient:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="patient not found")
    return _fhir_response(
        diagnostic_report_from_diagnosis(diag, diag.exam, patient)
    )


@router.get(
    "/Patient/{patient_id}/bundle",
    summary="FHIR Bundle — Patient + Observations + DiagnosticReports",
    responses={200: {"content": {FHIR_JSON: {}}}},
)
async def fhir_patient_bundle(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(current_user_strict),
) -> JSONResponse:
    patient = await db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="patient not found")

    images = (
        await db.scalars(
            select(EyeImage)
            .where(EyeImage.patient_id == patient_id)
            .order_by(EyeImage.uploaded_at.desc())
            .limit(20)
        )
    ).all()

    diagnoses = (
        await db.scalars(
            select(Diagnosis)
            .join(EyeExam, Diagnosis.exam_id == EyeExam.id)
            .where(EyeExam.patient_id == patient_id)
            .order_by(Diagnosis.created_at.desc())
            .limit(20)
        )
    ).all()

    obs_list = [observation_from_image(img, patient) for img in images if img.analyzed]
    report_list = []
    for d in diagnoses:
        if d.exam_id:
            exam = await db.get(EyeExam, d.exam_id)
            if exam:
                report_list.append(
                    diagnostic_report_from_diagnosis(d, exam, patient)
                )

    bundle = patient_bundle(
        patient, observations=obs_list, reports=report_list
    )
    log.info(
        "FHIR bundle patient=%s entries=%s",
        patient_id[:8],
        bundle.get("total"),
    )
    return _fhir_response(bundle)
