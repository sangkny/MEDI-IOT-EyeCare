# MEDI-IOT-EyeCare/api/patients.py
"""
환자 관리 API

POST   /api/v1/patients                — 환자 등록
GET    /api/v1/patients/{id}           — 환자 조회
GET    /api/v1/patients                — 환자 목록 (페이징)
DELETE /api/v1/patients/{id}           — 환자 비활성화 (soft delete)
GET    /api/v1/patients/{id}/exams     — 환자별 검사 목록
GET    /api/v1/patients/{id}/history   — 환자 이력 전체 [Week 3]
GET    /api/v1/patients/{id}/trend     — 시력/안압 추이 분석 [Week 3]
GET    /api/v1/patients/{id}/reports   — AI 진단 보고서 목록 [Week 3]
"""
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models.medical import Patient, EyeExam, Diagnosis
from schemas.medical import PatientCreate, PatientResponse, ExamResponse, DiagnosisResponse
from services.trend_analyzer import TrendAnalyzer
from services.cache import get_cache, CacheService

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
    response_description="등록된 환자 정보 (이름은 마스킹 처리)",
)
async def create_patient(
    data: PatientCreate,
    db: AsyncSession = Depends(get_db),
) -> PatientResponse:
    """
    환자를 등록합니다.

    - `patient_code`는 병원 내부 번호로 **고유값**이어야 합니다
    - `name`은 AES-256으로 암호화하여 저장됩니다
    - 응답의 `name_masked`는 첫 글자만 노출 (예: 홍길동 → 홍**)
    - `primary_diagnosis_code`는 ICD-10 형식 검증 (예: `H36.0`)
    """
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
    response_description="환자 상세 정보 + 검사 횟수",
)
async def get_patient(
    patient_id: str = Path(
        description="환자 UUID 또는 patient_code (예: P123456)",
        examples=["P123456"],
    ),
    db: AsyncSession = Depends(get_db),
) -> PatientResponse:
    """
    UUID 또는 `patient_code`로 환자를 조회합니다.

    - `patient_id` 파라미터에 UUID 또는 `P123456` 형식 모두 허용
    - `exam_count`: 해당 환자의 전체 검사 기록 수
    """
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


# ════════════════════════════════════════════════════════════
# Week 3 신규 — 이력/추이/보고서
# ════════════════════════════════════════════════════════════

@router.get(
    "/{patient_id}/history",
    response_model=dict,
    summary="환자 전체 이력 조회 [Week 3]",
    description="""
환자의 전체 의료 이력을 한 번에 조회합니다.

반환 데이터:
- `patient`: 환자 기본 정보
- `exams`: 검사 기록 목록 (최근 20개)
- `diagnoses`: AI 진단 결과 목록
- `summary`: 총계 요약
    """,
)
async def get_patient_history(
    patient_id: str,
    db:         AsyncSession = Depends(get_db),
) -> dict:
    """환자의 검사 + 진단 전체 이력을 반환합니다."""
    patient = await db.scalar(
        select(Patient).where(
            (Patient.id == patient_id) | (Patient.patient_code == patient_id)
        )
    )
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"환자를 찾을 수 없습니다: {patient_id}")

    exams = (await db.scalars(
        select(EyeExam)
        .where(EyeExam.patient_id == patient.id)
        .order_by(EyeExam.exam_date.desc())
        .limit(20)
    )).all()

    diagnoses = (await db.scalars(
        select(Diagnosis)
        .where(Diagnosis.exam_id.in_([e.id for e in exams]))
        .order_by(Diagnosis.created_at.desc())
    )).all()

    return {
        "patient": {
            "id":           patient.id,
            "patient_code": patient.patient_code,
            "is_active":    patient.is_active,
        },
        "exams":     [ExamResponse.model_validate(e).model_dump() for e in exams],
        "diagnoses": [DiagnosisResponse.model_validate(d).model_dump() for d in diagnoses],
        "summary": {
            "total_exams":      len(exams),
            "total_diagnoses":  len(diagnoses),
            "latest_exam_date": exams[0].exam_date.isoformat() if exams else None,
        },
    }


@router.get(
    "/{patient_id}/trend",
    response_model=dict,
    summary="시력/안압 추이 분석 [Week 3]",
    description="""
환자의 시력/안압 시계열 추이를 분석합니다.

**캐싱**: Redis 1시간 캐시 — 새 검사 등록 시 자동 무효화

반환 데이터:
- `iop_trend`: 안압 추이 (improving/stable/worsening)
- `vision_trend`: 시력 추이
- `overall_status`: 종합 상태
- `iop_series`: 안압 시계열 [{date, left, right, avg}]
- `vision_series`: 시력 시계열 [{date, left, right}]
- `alerts`: 악화 징후 경고 목록
- `recommendations`: 추적 관찰 권고
    """,
)
async def get_patient_trend(
    patient_id: str,
    db:         AsyncSession = Depends(get_db),
    cache:      CacheService = Depends(get_cache),
) -> dict:
    """시력/안압 추이 분석 (Redis 캐싱 적용)."""
    patient = await db.scalar(
        select(Patient).where(
            (Patient.id == patient_id) | (Patient.patient_code == patient_id)
        )
    )
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"환자를 찾을 수 없습니다: {patient_id}")

    pid = patient.id

    # Redis 캐시 확인
    cached = await cache.get_trend(pid)
    if cached:
        cached["cached"] = True
        return cached

    # 추이 분석 실행
    analyzer = TrendAnalyzer(db)
    trend    = await analyzer.analyze(pid)

    result = {
        "patient_id":       pid,
        "exam_count":       trend.exam_count,
        "date_range":       {
            "from": trend.date_range[0].isoformat() if trend.date_range else None,
            "to":   trend.date_range[1].isoformat() if trend.date_range else None,
        },
        "iop_trend":        trend.iop_trend,
        "vision_trend":     trend.vision_trend,
        "overall_status":   trend.overall_status,
        "iop_series":       trend.iop_series,
        "vision_series":    trend.vision_series,
        "diagnosis_history": trend.diagnosis_history,
        "alerts":           trend.alerts,
        "recommendations":  trend.recommendations,
        "cached":           False,
    }

    # 캐시 저장
    await cache.set_trend(pid, result)
    return result


@router.get(
    "/{patient_id}/reports",
    response_model=list[dict],
    summary="AI 진단 보고서 목록 [Week 3]",
    description="""
환자의 AI 진단 보고서 전체 목록을 반환합니다.

- `ontology_passed=true`: OntologyValidator 검증 통과
- `confidence_score`: 0.0~1.0 (0.85+ = 고신뢰)
    """,
)
async def get_patient_reports(
    patient_id: str,
    only_passed: bool = False,
    db:          AsyncSession = Depends(get_db),
) -> list[dict]:
    """환자의 AI 진단 보고서 목록 (ontology 검증 필터 가능)."""
    patient = await db.scalar(
        select(Patient).where(
            (Patient.id == patient_id) | (Patient.patient_code == patient_id)
        )
    )
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"환자를 찾을 수 없습니다: {patient_id}")

    exam_ids = (await db.scalars(
        select(EyeExam.id).where(EyeExam.patient_id == patient.id)
    )).all()

    q = select(Diagnosis).where(Diagnosis.exam_id.in_(exam_ids))
    if only_passed:
        q = q.where(Diagnosis.ontology_passed == True)  # noqa: E712
    q = q.order_by(Diagnosis.created_at.desc())

    diagnoses = (await db.scalars(q)).all()
    return [DiagnosisResponse.model_validate(d).model_dump() for d in diagnoses]
