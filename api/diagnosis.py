# MEDI-IOT-EyeCare/api/diagnosis.py
"""
안과 진단 API — shared-libraries Orchestrator(CONSENSUS) 연동

POST /api/v1/diagnosis          — AI 진단 보고서 생성
GET  /api/v1/diagnosis/{id}     — 진단 결과 조회
POST /api/v1/diagnosis/exam     — 검사 기록 등록
"""
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.medical import EyeExam, Diagnosis, ReportStatusEnum
from schemas.medical import (
    DiagnosisRequest, DiagnosisResponse,
    ExamCreate, ExamResponse,
)
from services.report_gen import ReportGenerator

log = logging.getLogger("api.diagnosis")
router = APIRouter()


@router.post(
    "/exam",
    response_model=ExamResponse,
    status_code=status.HTTP_201_CREATED,
    summary="검사 기록 등록",
)
async def create_exam(
    data: ExamCreate,
    db: AsyncSession = Depends(get_db),
) -> ExamResponse:
    """안과 검사 기록을 등록합니다."""
    exam = EyeExam(
        id=str(uuid.uuid4()),
        patient_id=data.patient_id,
        exam_type=data.exam_type,
        exam_date=data.exam_date,
        icd_code=data.icd_code,
        iop_left=data.iop_left,
        iop_right=data.iop_right,
        visual_acuity_left=data.visual_acuity_left,
        visual_acuity_right=data.visual_acuity_right,
        raw_findings=data.raw_findings,
        report_status=ReportStatusEnum.PENDING,
    )
    db.add(exam)
    await db.flush()

    log.info(f"검사 등록: {exam.id} (type={exam.exam_type})")
    return ExamResponse.model_validate(exam)


@router.post(
    "/",
    response_model=DiagnosisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="AI 진단 보고서 생성",
    description="""
    shared-libraries Orchestrator(CONSENSUS 전략)를 사용하여
    안과 AI 진단 보고서를 생성합니다.

    - FAST 모델: 초안 생성 (gemma-4-e4b)
    - HEAVY 모델: 의료 정확성 검토 (gemma-4-26b-a4b)
    - OntologyValidator: MEDICAL 도메인 규칙 검증

    처리 시간: 약 1~3분 (CONSENSUS 전략)
    """,
)
async def create_diagnosis(
    req: DiagnosisRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    report_gen: ReportGenerator = Depends(ReportGenerator),
) -> DiagnosisResponse:
    """
    검사 기록 기반 AI 진단 보고서를 생성합니다.
    CONSENSUS 전략으로 FAST + HEAVY 모델이 동시에 검증합니다.
    """
    # 검사 기록 조회
    exam = await db.scalar(
        select(EyeExam).where(EyeExam.id == req.exam_id)
    )
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"검사 기록을 찾을 수 없습니다: {req.exam_id}",
        )

    # 진단 보고서 생성 (LLM 호출)
    exam.report_status = ReportStatusEnum.GENERATING
    await db.flush()

    try:
        result = await report_gen.generate(
            exam=exam,
            strategy=req.strategy,
            additional_context=req.additional_context,
        )

        diagnosis = Diagnosis(
            id=str(uuid.uuid4()),
            exam_id=exam.id,
            diagnosis_code=result["diagnosis_code"],
            diagnosis_name=result["diagnosis_name"],
            severity=result["severity"],
            report=result["report"],
            treatment_plan=result.get("treatment_plan"),
            llm_model=result.get("llm_model"),
            llm_iterations=result.get("iterations", 1),
            llm_latency_ms=result.get("latency_ms"),
            ontology_passed=result.get("ontology_passed", False),
            confidence_score=result.get("confidence_score"),
        )
        db.add(diagnosis)

        exam.ai_summary = result["report"][:500] if result["report"] else None
        exam.report_status = ReportStatusEnum.COMPLETED
        await db.flush()

        log.info(
            f"진단 완료: {diagnosis.id} | "
            f"code={diagnosis.diagnosis_code} | "
            f"iter={diagnosis.llm_iterations} | "
            f"{diagnosis.llm_latency_ms:.0f}ms"
        )
        return DiagnosisResponse.model_validate(diagnosis)

    except Exception as e:
        exam.report_status = ReportStatusEnum.FAILED
        await db.flush()
        log.error(f"진단 생성 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"진단 보고서 생성 실패: {str(e)[:200]}",
        )


@router.get(
    "/{diagnosis_id}",
    response_model=DiagnosisResponse,
    summary="진단 결과 조회",
)
async def get_diagnosis(
    diagnosis_id: str,
    db: AsyncSession = Depends(get_db),
) -> DiagnosisResponse:
    """진단 결과를 조회합니다."""
    diagnosis = await db.scalar(
        select(Diagnosis).where(Diagnosis.id == diagnosis_id)
    )
    if not diagnosis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"진단 결과를 찾을 수 없습니다: {diagnosis_id}",
        )
    return DiagnosisResponse.model_validate(diagnosis)
