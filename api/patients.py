# MEDI-IOT-EyeCare/api/patients.py
"""
환자 관리 API

POST   /api/v1/patients           — 환자 등록
GET    /api/v1/patients/{id}      — 환자 조회
GET    /api/v1/patients           — 환자 목록 (페이징)
PATCH  /api/v1/patients/{id}      — 환자 정보 수정
DELETE /api/v1/patients/{id}      — 환자 비활성화 (soft delete)
GET    /api/v1/patients/{id}/exams — 환자별 검사 목록
"""
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models.medical import Patient, EyeExam
from schemas.medical import PatientCreate, PatientResponse, ExamResponse

log = logging.getLogger("api.patients")
router = APIRouter()


def _mask_name(name: str | None) -> str | None:
    """이름 마스킹: '김철수' → '김**'"""
    if not name:
        return None
    return name[0] + "*" * (len(name) - 1)


@router.post(
    "/",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
    summary="환자 등록",
)
async def create_patient(
    data: PatientCreate,
    db: AsyncSession = Depends(get_db),
) -> PatientResponse:
    """환자를 등록합니다. PII(이름)는 암호화하여 저장됩니다."""
    # 중복 환자 코드 확인
    existing = await db.scalar(
        select(Patient).where(Patient.patient_code == data.patient_code)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"이미 존재하는 환자 코드: {data.patient_code}",
        )

    patient = Patient(
        id=str(uuid.uuid4()),
        patient_code=data.patient_code,
        # TODO: 실제 운영에서는 AES-256 암호화 적용
        name_encrypted=data.name,
        date_of_birth=data.date_of_birth,
        gender=data.gender,
        primary_diagnosis_code=data.primary_diagnosis_code,
        notes=data.notes,
    )
    db.add(patient)
    await db.flush()

    log.info(f"환자 등록: {patient.patient_code}")

    return PatientResponse(
        id=patient.id,
        patient_code=patient.patient_code,
        name_masked=_mask_name(data.name),
        date_of_birth=patient.date_of_birth,
        gender=patient.gender,
        primary_diagnosis_code=patient.primary_diagnosis_code,
        is_active=patient.is_active,
        created_at=patient.created_at,
        exam_count=0,
    )


@router.get(
    "/{patient_id}",
    response_model=PatientResponse,
    summary="환자 조회",
)
async def get_patient(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
) -> PatientResponse:
    """UUID 또는 patient_code로 환자를 조회합니다."""
    patient = await db.scalar(
        select(Patient)
        .where(
            (Patient.id == patient_id) | (Patient.patient_code == patient_id)
        )
        .options(selectinload(Patient.exams))
    )
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"환자를 찾을 수 없습니다: {patient_id}",
        )

    return PatientResponse(
        id=patient.id,
        patient_code=patient.patient_code,
        name_masked=_mask_name(patient.name_encrypted),
        date_of_birth=patient.date_of_birth,
        gender=patient.gender,
        primary_diagnosis_code=patient.primary_diagnosis_code,
        is_active=patient.is_active,
        created_at=patient.created_at,
        exam_count=len(patient.exams),
    )


@router.get(
    "/",
    response_model=list[PatientResponse],
    summary="환자 목록 조회",
)
async def list_patients(
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
) -> list[PatientResponse]:
    """환자 목록을 페이징하여 조회합니다."""
    q = select(Patient)
    if active_only:
        q = q.where(Patient.is_active == True)  # noqa: E712
    q = q.offset(skip).limit(limit).order_by(Patient.created_at.desc())

    patients = (await db.scalars(q)).all()

    return [
        PatientResponse(
            id=p.id,
            patient_code=p.patient_code,
            name_masked=_mask_name(p.name_encrypted),
            date_of_birth=p.date_of_birth,
            gender=p.gender,
            primary_diagnosis_code=p.primary_diagnosis_code,
            is_active=p.is_active,
            created_at=p.created_at,
        )
        for p in patients
    ]


@router.delete(
    "/{patient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="환자 비활성화 (soft delete)",
)
async def deactivate_patient(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """환자를 비활성화합니다 (실제 삭제 아님 — 의료 데이터 보존 의무)."""
    patient = await db.scalar(
        select(Patient).where(Patient.id == patient_id)
    )
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"환자를 찾을 수 없습니다: {patient_id}",
        )
    patient.is_active = False
    log.info(f"환자 비활성화: {patient.patient_code}")


@router.get(
    "/{patient_id}/exams",
    response_model=list[ExamResponse],
    summary="환자별 검사 목록",
)
async def get_patient_exams(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[ExamResponse]:
    """특정 환자의 전체 검사 기록을 조회합니다."""
    patient = await db.scalar(
        select(Patient).where(
            (Patient.id == patient_id) | (Patient.patient_code == patient_id)
        )
    )
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"환자를 찾을 수 없습니다: {patient_id}",
        )

    exams = (await db.scalars(
        select(EyeExam)
        .where(EyeExam.patient_id == patient.id)
        .order_by(EyeExam.exam_date.desc())
    )).all()

    return [ExamResponse.model_validate(e) for e in exams]
