# MEDI-IOT-EyeCare/api/diagnosis.py
"""
안과 진단 API — shared-libraries Orchestrator(CONSENSUS) 연동

POST /api/v1/diagnosis          — AI 진단 보고서 생성
GET  /api/v1/diagnosis/{id}     — 진단 결과 조회
POST /api/v1/diagnosis/exam     — 검사 기록 등록
POST /api/v1/diagnosis/explain  — CNN + LLM 통합 설명 (R4-ML+)
POST /api/v1/diagnosis/comprehensive — 설명 + 병원 + MEDI-EYE 추천
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import get_db
from events import EVENT_MEDICAL_DIAGNOSIS_COMPLETED, publish_platform_event
from auth.policy import policy_require
from models.medical import EyeExam, Diagnosis, DiagnosisSeverityEnum, ReportStatusEnum
from schemas.integrated_diagnosis import (
    ComprehensiveDiagnosisRequest,
    ComprehensiveDiagnosisResponse,
    DeviceRecommendation,
    DiagnosisExplainRequest,
    DiagnosisExplainResponse,
    HospitalRecommendation,
)
from schemas.medical import (
    DiagnosisRequest, DiagnosisResponse,
    ExamCreate, ExamResponse,
)
from services.integrated_diagnosis import decode_image_base64, run_integrated_explain
from services.report_gen import ReportGenerator

log = logging.getLogger("api.diagnosis")
router = APIRouter()


async def _emit_medical_diagnosis_completed(
    *,
    redis_url: str,
    diagnosis_id: str,
    exam_id: str,
    diagnosis_code: str,
) -> None:
    try:
        await publish_platform_event(
            redis_url,
            EVENT_MEDICAL_DIAGNOSIS_COMPLETED,
            {
                "diagnosis_id":    diagnosis_id,
                "exam_id":         exam_id,
                "diagnosis_code":  diagnosis_code,
            },
        )
    except Exception as e:
        log.warning("Redis 이벤트 medical.diagnosis.completed 발행 스킵: %s", e)
@router.post(
    "/exam",
    response_model=ExamResponse,
    status_code=status.HTTP_201_CREATED,
    summary="검사 기록 등록",
    response_description="등록된 검사 기록 (AI 분석 전 상태, report_status=pending)",
)
async def create_exam(
    data: ExamCreate,
    db: AsyncSession = Depends(get_db),
) -> ExamResponse:
    """
    안과 검사 기록을 등록합니다.

    등록 후 `POST /diagnosis/ai-analyze`를 호출하면 AI 진단 보고서가 생성됩니다.

    **지원 검사 종류**:
    | exam_type | 설명 |
    |-----------|------|
    | fundus | 안저 촬영 (당뇨망막병증, 녹내장 선별) |
    | oct | 빛간섭단층촬영 (황반 질환, 시신경 분석) |
    | visual_field | 시야 검사 (녹내장 진행 모니터링) |
    | slit_lamp | 세극등 검사 (각막, 수정체, 전방) |
    | refraction | 굴절 검사 (근시, 난시, 원시 측정) |
    | iop | 안압 검사 (녹내장 위험 평가) |
    """
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


_AI_ANALYZE_DESC = """
검사 기록 기반으로 AI 진단 보고서를 생성합니다.

**처리 파이프라인 (CONSENSUS 전략)**:
```
검사 소견 입력
    ↓
PlannerAgent (gemma-4-e4b)     ← 진단 작업 계획 수립
    ↓
GeneratorAgent (gemma-4-e4b)   ← 초안 보고서 생성
    ↓
ReviewerAgent (gemma-4-26b-a4b) + OntologyValidator (MEDICAL)
    ↓ PASS → 보고서 확정
    ↓ FAIL → FixerAgent → 재검토 (최대 2회)
    ↓
DiagnosisResponse 반환
```

**예상 처리 시간**: 1~3분 (CONSENSUS 전략, LM Studio 기준)

**OntologyValidator 검증 항목**:
- Semantic: 의학 용어 정합성
- Structural: 보고서 구조 완결성
- Constraint: PII 미포함 여부
- Dependency: ICD 코드 ↔ 진단명 일치

> **주의**: `ontology_passed=false`인 경우 보고서가 반환되더라도
> 의사의 추가 검토가 필요합니다.
"""

@router.post(
    "/",
    response_model=DiagnosisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="AI 진단 보고서 생성",
    description=_AI_ANALYZE_DESC,
    response_description="생성된 진단 보고서 (OntologyValidator 검증 완료)",
)
@router.post(
    "/ai-analyze",
    response_model=DiagnosisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="AI 진단 보고서 생성 (명시적 경로)",
    description=_AI_ANALYZE_DESC,
    response_description="생성된 진단 보고서 (OntologyValidator 검증 완료)",
)
async def create_diagnosis(
    req: DiagnosisRequest,
    db: AsyncSession = Depends(get_db),
    report_gen: ReportGenerator = Depends(ReportGenerator),
    _: dict = Depends(policy_require("medi-iot", "ai_analyze")),
) -> DiagnosisResponse:
    """AI 진단 보고서 생성 — `POST /diagnosis/ai-analyze` 와 동일"""
    return await _run_diagnosis(req, db, report_gen)


async def _run_diagnosis(
    req: DiagnosisRequest,
    db: AsyncSession,
    report_gen: ReportGenerator,
) -> DiagnosisResponse:
    """AI 진단 보고서 생성 공통 로직"""
    exam = await db.scalar(
        select(EyeExam).where(EyeExam.id == req.exam_id)
    )
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"검사 기록을 찾을 수 없습니다: {req.exam_id}",
        )

    exam.report_status = ReportStatusEnum.GENERATING
    await db.flush()

    try:
        result = await report_gen.generate(
            exam=exam,
            strategy=req.strategy,
            additional_context=req.additional_context,
            db=db,
            use_rag=True,
        )

        sev_raw = str(result.get("severity") or "mild").lower()
        try:
            sev_enum = DiagnosisSeverityEnum(sev_raw)
        except ValueError:
            sev_enum = DiagnosisSeverityEnum.MILD

        diagnosis = Diagnosis(
            id=str(uuid.uuid4()),
            exam_id=exam.id,
            diagnosis_code=result["diagnosis_code"],
            diagnosis_name=result["diagnosis_name"],
            severity=sev_enum,
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

        redis_url = (get_settings().redis_url or "").strip()
        if redis_url:
            asyncio.create_task(
                _emit_medical_diagnosis_completed(
                    redis_url=redis_url,
                    diagnosis_id=diagnosis.id,
                    exam_id=exam.id,
                    diagnosis_code=diagnosis.diagnosis_code,
                ),
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


def _hospitals_to_schema(candidates) -> list[HospitalRecommendation]:
    return [
        HospitalRecommendation(
            name=h.name,
            address=h.address,
            distance_km=h.distance_km,
            specialty=h.specialty,
            phone=h.phone,
            evaluation_score=h.evaluation_score,
            map_url=h.map_url,
            urgency=h.urgency,
            data_source=h.data_source,
        )
        for h in candidates
    ]


def _devices_to_schema(devices) -> list[DeviceRecommendation]:
    return [
        DeviceRecommendation(
            type=d.type,
            device=d.device,
            reason=d.reason,
            link=d.link,
            nutrition=d.nutrition,
        )
        for d in devices
    ]


def _explanation_to_response(
    explanation,
    hospitals: list,
    devices: list | None = None,
    *,
    ontology_passed: bool | None = None,
    audit_trail: dict | None = None,
    decision_mode: str = "legacy",
) -> DiagnosisExplainResponse | ComprehensiveDiagnosisResponse:
    base = {
        "dr_grade": explanation.dr_grade,
        "confidence": explanation.confidence,
        "icd10_code": explanation.icd10_code,
        "severity": explanation.severity,
        "patient_explanation": explanation.patient_explanation,
        "clinical_summary": explanation.clinical_summary,
        "recommended_actions": explanation.recommended_actions,
        "nearby_hospitals": _hospitals_to_schema(hospitals),
        "ontology_passed": (
            explanation.ontology_passed
            if ontology_passed is None
            else ontology_passed
        ),
        "model_used": explanation.model_used,
        "decision_mode": decision_mode,
        "audit_trail": audit_trail or {},
    }
    if devices is not None:
        return ComprehensiveDiagnosisResponse(
            **base,
            device_recommendations=_devices_to_schema(devices),
        )
    return DiagnosisExplainResponse(**base)


@router.post(
    "/explain",
    response_model=DiagnosisExplainResponse,
    summary="CNN + LLM 통합 설명",
    status_code=status.HTTP_200_OK,
)
async def explain_diagnosis(
    body: DiagnosisExplainRequest,
    _: dict = Depends(policy_require("medi-iot", "ai_analyze")),
) -> DiagnosisExplainResponse:
    """
    안저 이미지 → CNN DR 등급 → LLM 환자/임상 설명 → Ontology 검증.
    ``location`` 이 있으면 주변 병원 추천을 포함합니다.
    """
    try:
        image_bytes = decode_image_base64(body.image_base64)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    loc = None
    if body.location:
        loc = (body.location.lat, body.location.lng)

    try:
        explanation, hospitals, _ = await run_integrated_explain(
            image_bytes,
            patient_lang=body.lang,
            patient_id=body.patient_id,
            location=loc,
            radius_km=body.radius_km,
            include_devices=False,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"CNN model unavailable: {exc}",
        ) from exc
    except Exception as exc:
        log.error("explain_diagnosis failed: %s", exc)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"통합 설명 실패: {str(exc)[:200]}",
        ) from exc

    onto, audit, mode = await _apply_four_agent(explanation, body.patient_id)
    return _explanation_to_response(
        explanation,
        hospitals,
        ontology_passed=onto,
        audit_trail=audit,
        decision_mode=mode,
    )


async def _apply_four_agent(explanation, patient_id: str | None):
    from services.diagnosis_pipeline import apply_four_agent_decision

    return await apply_four_agent_decision(
        dr_grade=explanation.dr_grade,
        confidence=explanation.confidence,
        icd10_code=explanation.icd10_code,
        patient_explanation=explanation.patient_explanation,
        clinical_summary=explanation.clinical_summary,
        ontology_passed_legacy=explanation.ontology_passed,
        patient_id=patient_id,
    )


@router.post(
    "/comprehensive",
    response_model=ComprehensiveDiagnosisResponse,
    summary="통합 진단 (CNN+LLM+병원+MEDI-EYE)",
    status_code=status.HTTP_200_OK,
)
async def comprehensive_diagnosis(
    body: ComprehensiveDiagnosisRequest,
    _: dict = Depends(policy_require("medi-iot", "ai_analyze")),
) -> ComprehensiveDiagnosisResponse:
    """explain + MEDI-EYE-h/w 기기 추천."""
    try:
        image_bytes = decode_image_base64(body.image_base64)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    loc = (37.5665, 126.9780)
    if body.location:
        loc = (body.location.lat, body.location.lng)

    try:
        explanation, hospitals, devices = await run_integrated_explain(
            image_bytes,
            patient_lang=body.lang,
            patient_id=body.patient_id,
            location=loc,
            radius_km=body.radius_km,
            include_devices=True,
            patient_profile=body.patient_profile,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"CNN model unavailable: {exc}",
        ) from exc
    except Exception as exc:
        log.error("comprehensive_diagnosis failed: %s", exc)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"통합 진단 실패: {str(exc)[:200]}",
        ) from exc

    onto, audit, mode = await _apply_four_agent(explanation, body.patient_id)
    return _explanation_to_response(
        explanation,
        hospitals,
        devices,
        ontology_passed=onto,
        audit_trail=audit,
        decision_mode=mode,
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
