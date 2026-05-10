"""안저 등 이미지 전처리 + VISION 파이프라인 (Ontology MEDICAL)."""
from __future__ import annotations

import base64
import io
import logging
import tempfile
from pathlib import Path

from ontology.validator import OntologyValidator

log = logging.getLogger("services.image_processor")


class ImageProcessor:
    """PIL 리사이즈 · EXIF 정리 후 EyeAnalyzer 또는 직접 VISION 검증."""

    def __init__(self, max_edge: int = 1024) -> None:
        self._max = max_edge

    def preprocess(self, image_path: str | Path) -> tuple[bytes, str]:
        from PIL import Image, ImageOps

        path = Path(image_path)
        im = Image.open(path)
        im = ImageOps.exif_transpose(im)
        im = im.convert("RGB")
        im.thumbnail((self._max, self._max))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=90, optimize=True)
        return buf.getvalue(), "jpeg"

    def preprocess_to_base64(self, image_path: str | Path) -> str:
        raw, _ = self.preprocess(image_path)
        return base64.standard_b64encode(raw).decode("ascii")

    async def analyze_with_vision(
        self,
        image_path: str | Path,
        exam_type: str = "fundus",
    ):
        """EyeAnalyzer 재사용 → AnalysisResult 반환."""
        from services.eye_analyzer import AnalysisResult, EyeAnalyzer

        raw_jpeg, _ = self.preprocess(image_path)

        fd, tmp_path = tempfile.mkstemp(suffix=".jpg")
        Path(tmp_path).write_bytes(raw_jpeg)
        try:
            ea: EyeAnalyzer = EyeAnalyzer()
            res: AnalysisResult = await ea.analyze_image_file(
                tmp_path,
                exam_type=exam_type,
            )
            return res
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    async def validate_medical_placeholder(
        self,
        diagnosis_code: str,
        examination_date: str,
        *,
        eye_condition: str = "retinopathy_related",
        patient_id: str = "VISION-ANALYSIS",
        doctor_id: str = "AI-VISION-001",
    ):
        """for_medical() 구조 검증 헬퍼 (PII·ICD 패턴 확인)."""
        data = {
            "patient_id":       patient_id,
            "doctor_id":        doctor_id,
            "examination_date": examination_date,
            "diagnosis_code":   diagnosis_code,
            "eye_condition":    eye_condition,
        }
        vr = await OntologyValidator.for_medical().validate(data)
        return vr
