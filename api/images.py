# MEDI-IOT-EyeCare/api/images.py
"""
안과 이미지 업로드 API [Week 3 신규]

POST /api/v1/images/upload      — 이미지 업로드 + 선택적 VISION 분석
GET  /api/v1/images/{image_id}  — 이미지 메타데이터 조회
GET  /api/v1/images/{image_id}/analysis — 분석 결과 조회
POST /api/v1/images/{image_id}/analyze  — 업로드된 이미지 분석 트리거
GET  /api/v1/patients/{patient_id}/images — 환자별 이미지 목록
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings, Settings
from database import get_db
from models.medical import EyeImage, Patient, ImageTypeEnum

log = logging.getLogger("api.images")
router = APIRouter()

# 허용 이미지 타입
ALLOWED_MIME = {"image/jpeg", "image/png", "image/tiff", "image/bmp"}
MAX_FILE_MB  = 20


# ════════════════════════════════════════════════════════════
# 스키마
# ════════════════════════════════════════════════════════════

class ImageResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id":               "d4e5f6a7-b8c9-0123-defa-456789012345",
                "patient_id":       "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "image_type":       "fundus",
                "file_name":        "fundus_right_eye.jpg",
                "file_size":        2048576,
                "mime_type":        "image/jpeg",
                "analyzed":         False,
                "analysis_icd_code": None,
                "analysis_severity": None,
                "uploaded_at":      "2026-05-09T16:30:00Z",
            }
        },
    )

    id:               str
    patient_id:       str
    exam_id:          str | None
    image_type:       str
    file_name:        str
    file_size:        int
    mime_type:        str
    analyzed:         bool
    analysis_icd_code: str | None
    analysis_severity: str | None
    uploaded_at:      datetime
    analyzed_at:      datetime | None = None


class AnalysisResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "image_id":    "d4e5f6a7-b8c9-0123-defa-456789012345",
                "analyzed":    True,
                "condition":   "diabetic_retinopathy",
                "icd10_code":  "H36.0",
                "severity":    "moderate",
                "confidence":  0.85,
                "raw_analysis": "안저 촬영 분석 결과: 황반 주위 점상출혈 관찰...",
            }
        }
    )

    image_id:     str
    analyzed:     bool
    condition:    str | None
    condition_kr: str | None
    icd10_code:   str | None
    severity:     str | None
    confidence:   float | None
    raw_analysis: str | None
    ontology_passed: bool = False


# ════════════════════════════════════════════════════════════
# 헬퍼
# ════════════════════════════════════════════════════════════

def _get_upload_dir(settings: Settings) -> Path:
    """레거시 helper — local 백엔드에서만 의미 있음. ``UPLOAD_DIR`` env 존중."""
    import os
    upload_dir = Path(os.getenv("UPLOAD_DIR", "/app/uploads"))
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


async def _save_upload(
    file: UploadFile,
    patient_id: str,
    settings: Settings,
) -> tuple[str, int]:
    """업로드 파일 저장 → (저장 경로 문자열, 파일 크기).

    D R2 Day 3 — ``services.image_storage.get_image_storage`` 가 env 토글
    (``STORAGE_BACKEND=local|s3``) 에 따라 backend 를 선택. local 동작은
    기존과 동일 (디스크 ``/app/uploads/{patient_id}/<uuid>.jpg``).
    S3 인 경우 ``s3://bucket/medi/{patient_id}/<uuid>.jpg`` 문자열을 반환.
    """
    from services.image_storage import get_image_storage

    content = await file.read()
    storage = get_image_storage()
    file_path = await storage.save(
        content,
        patient_id=patient_id,
        filename_hint=file.filename or "upload.jpg",
    )
    return file_path, len(content)


# ════════════════════════════════════════════════════════════
# 엔드포인트
# ════════════════════════════════════════════════════════════

@router.post(
    "/upload",
    response_model=ImageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="안과 이미지 업로드",
    description="""
안과 이미지(안저사진, OCT 등)를 업로드합니다.

**지원 형식**: JPEG, PNG, TIFF, BMP (최대 20MB)

**image_type 선택**:
| 값 | 설명 |
|----|------|
| fundus | 안저 촬영 |
| oct | 빛간섭단층촬영 |
| slit_lamp | 세극등 검사 |
| visual_field | 시야 검사 스캔 |
| other | 기타 |

`auto_analyze=true` 전달 시 업로드 즉시 VISION 모델 분석을 수행합니다.
    """,
)
async def upload_image(
    file:         UploadFile = File(..., description="이미지 파일 (JPEG/PNG/TIFF)"),
    patient_id:   str        = Form(..., description="환자 UUID"),
    image_type:   str        = Form("fundus", description="이미지 종류"),
    exam_id:      str | None = Form(None, description="연관 검사 UUID (선택)"),
    auto_analyze: bool       = Form(False, description="업로드 즉시 분석 여부"),
    db:           AsyncSession = Depends(get_db),
    settings:     Settings    = Depends(get_settings),
) -> ImageResponse:
    """안과 이미지를 업로드하고 선택적으로 VISION 모델 분석을 수행합니다."""

    # 환자 존재 확인
    patient = await db.scalar(
        select(Patient).where(Patient.id == patient_id)
    )
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"환자를 찾을 수 없습니다: {patient_id}",
        )

    # MIME 타입 검증
    mime = file.content_type or "image/jpeg"
    if mime not in ALLOWED_MIME:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"지원하지 않는 이미지 형식: {mime}. 허용: {ALLOWED_MIME}",
        )

    # image_type 검증
    try:
        img_type_enum = ImageTypeEnum(image_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"유효하지 않은 image_type: {image_type}",
        )

    # 파일 저장 (storage backend: local|s3)
    file_path, file_size = await _save_upload(file, patient_id, settings)

    # 파일 크기 제한 (20MB) — 초과 시 storage 백엔드의 delete 사용
    if file_size > MAX_FILE_MB * 1024 * 1024:
        from services.image_storage import get_image_storage
        try:
            await get_image_storage().delete(file_path)
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"파일 크기 초과: {file_size // 1024 // 1024}MB > {MAX_FILE_MB}MB",
        )

    image = EyeImage(
        id=str(uuid.uuid4()),
        patient_id=patient_id,
        exam_id=exam_id,
        image_type=img_type_enum,
        file_path=file_path,
        file_name=file.filename or Path(file_path).name,
        file_size=file_size,
        mime_type=mime,
    )
    db.add(image)
    await db.flush()

    log.info(f"이미지 업로드: {image.id} (type={image_type}, size={file_size}B)")

    # 자동 분석
    if auto_analyze:
        image = await _run_image_analysis(image, db)

    return ImageResponse.model_validate(image)


@router.get(
    "/{image_id}",
    response_model=ImageResponse,
    summary="이미지 메타데이터 조회",
)
async def get_image(
    image_id: str,
    db: AsyncSession = Depends(get_db),
) -> ImageResponse:
    """업로드된 이미지 메타데이터를 조회합니다."""
    image = await db.scalar(select(EyeImage).where(EyeImage.id == image_id))
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"이미지를 찾을 수 없습니다: {image_id}",
        )
    return ImageResponse.model_validate(image)


@router.get(
    "/{image_id}/analysis",
    response_model=AnalysisResponse,
    summary="이미지 분석 결과 조회",
)
async def get_image_analysis(
    image_id: str,
    db: AsyncSession = Depends(get_db),
) -> AnalysisResponse:
    """VISION 모델 분석 결과를 조회합니다."""
    image = await db.scalar(select(EyeImage).where(EyeImage.id == image_id))
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"이미지를 찾을 수 없습니다: {image_id}",
        )

    if not image.analyzed or not image.analysis_result:
        return AnalysisResponse(
            image_id=image_id,
            analyzed=False,
            condition=None, condition_kr=None,
            icd10_code=None, severity=None,
            confidence=None, raw_analysis=None,
        )

    try:
        data = json.loads(image.analysis_result)
    except Exception:
        data = {"raw_analysis": image.analysis_result}

    return AnalysisResponse(
        image_id=image_id,
        analyzed=True,
        condition=data.get("condition"),
        condition_kr=data.get("condition_kr"),
        icd10_code=image.analysis_icd_code or data.get("icd10_code"),
        severity=image.analysis_severity or data.get("severity"),
        confidence=data.get("confidence"),
        raw_analysis=data.get("raw_analysis"),
        ontology_passed=data.get("ontology_passed", False),
    )


@router.post(
    "/{image_id}/analyze",
    response_model=AnalysisResponse,
    summary="이미지 VISION 분석 트리거",
    description="""
업로드된 이미지를 VISION 모델(gemma-4-26b-a4b)로 분석합니다.

**처리 시간**: 약 30~90초 (이미지 크기 + VISION 모델 응답 시간)

분석 결과:
- condition: 진단명 (diabetic_retinopathy 등)
- icd10_code: ICD-10 코드 (H36.0 등)
- severity: 중증도 (mild/moderate/severe)
- confidence: 신뢰도 (0.0~1.0)
    """,
)
async def analyze_image(
    image_id: str,
    db:       AsyncSession = Depends(get_db),
) -> AnalysisResponse:
    """업로드된 이미지를 VISION 모델로 분석합니다."""
    image = await db.scalar(select(EyeImage).where(EyeImage.id == image_id))
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"이미지를 찾을 수 없습니다: {image_id}",
        )

    # local backend 일 때만 존재성 사전 검증 (s3 는 HEAD 비용 회피)
    if not image.file_path.startswith("s3://") and not Path(image.file_path).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="이미지 파일이 서버에 없습니다.",
        )

    image = await _run_image_analysis(image, db)

    data = json.loads(image.analysis_result) if image.analysis_result else {}
    return AnalysisResponse(
        image_id=image_id,
        analyzed=image.analyzed,
        condition=data.get("condition"),
        condition_kr=data.get("condition_kr"),
        icd10_code=image.analysis_icd_code,
        severity=image.analysis_severity,
        confidence=data.get("confidence"),
        raw_analysis=data.get("raw_analysis"),
        ontology_passed=data.get("ontology_passed", False),
    )


@router.get(
    "/patient/{patient_id}",
    response_model=list[ImageResponse],
    summary="환자별 이미지 목록",
)
async def get_patient_images(
    patient_id: str,
    db:         AsyncSession = Depends(get_db),
) -> list[ImageResponse]:
    """환자의 전체 이미지 목록을 조회합니다."""
    images = (await db.scalars(
        select(EyeImage)
        .where(EyeImage.patient_id == patient_id)
        .order_by(EyeImage.uploaded_at.desc())
    )).all()
    return [ImageResponse.model_validate(img) for img in images]


# ════════════════════════════════════════════════════════════
# 분석 헬퍼
# ════════════════════════════════════════════════════════════

async def _run_image_analysis(
    image: EyeImage,
    db: AsyncSession,
) -> EyeImage:
    """EyeAnalyzer로 이미지 분석 실행 → EyeImage 업데이트"""
    from services.eye_analyzer import EyeAnalyzer

    try:
        analyzer = EyeAnalyzer()
        result   = await analyzer.analyze_image_file(
            file_path=image.file_path,
            exam_type=image.image_type.value,
        )

        image.analyzed        = True
        image.analyzed_at     = datetime.now(timezone.utc)
        image.analysis_icd_code = result.icd10_code
        image.analysis_severity = result.severity
        image.analysis_result   = json.dumps({
            "condition":       result.condition,
            "condition_kr":    result.condition_kr,
            "icd10_code":      result.icd10_code,
            "severity":        result.severity,
            "confidence":      result.confidence,
            "raw_analysis":    result.raw_analysis[:500],
            "ontology_passed": result.ontology_passed,
        }, ensure_ascii=False)

        log.info(
            f"이미지 분석 완료: {image.id} | "
            f"{result.icd10_code} | {result.severity}"
        )
    except Exception as e:
        log.error(f"이미지 분석 실패: {image.id} — {e}")
        image.analyzed      = False
        image.analysis_result = json.dumps({"error": str(e)[:200]})

    await db.flush()

    # D R2 Day 4 — CONSENSUS + 임계값 통과 시 자동 promote (best-effort)
    try:
        from services.auto_promote import try_auto_promote_for_image
        ap_result = await try_auto_promote_for_image(db, image)
        if ap_result.get("outcome") == "promoted":
            log.info(
                "자동 승격: image=%s diag=%s review=%s",
                image.id[:8],
                ap_result.get("diagnosis_id", "?")[:8],
                ap_result.get("review_id", "?")[:8],
            )
        else:
            log.debug("자동 승격 skip: %s", ap_result.get("reason"))
    except Exception as ap_exc:
        log.warning("자동 승격 실패(무시): %s", ap_exc)

    return image
