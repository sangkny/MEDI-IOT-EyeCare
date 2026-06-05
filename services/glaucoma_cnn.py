"""Glaucoma CNN 추론 — retinal_glaucoma_v2 ONNX."""
from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from schemas.integrated_diagnosis import (
    CupDiscRatioDetail,
    GlaucomaHeatmap,
    GlaucomaLesionAnnotation,
    GlaucomaResult,
)
from services.retinal_cnn import (
    DEFAULT_IMAGE_SIZE,
    preprocess_fundus_bytes,
    resolve_preprocess_mode,
)

log = logging.getLogger("services.glaucoma_cnn")

RiskLevel = Literal["LOW", "MODERATE", "HIGH"]


@dataclass(frozen=True)
class GlaucomaPrediction:
    probability: float
    label: str
    glaucoma_grade: int
    grade_label: str
    confidence: float
    risk_level: RiskLevel


def get_glaucoma_model_path() -> Path:
    root = Path((os.getenv("MEDI_APP_ROOT") or "/app").strip())
    raw = (os.getenv("MEDI_GLAUCOMA_MODEL_PATH") or "models/retinal_glaucoma_v2.onnx").strip()
    path = Path(raw) if Path(raw).is_absolute() else root / raw
    if path.suffix != ".onnx":
        onnx_alt = path.with_suffix(".onnx")
        if onnx_alt.is_file():
            return onnx_alt
    return path


def _meta_path(model_path: Path) -> Path:
    return model_path.with_name(model_path.stem + ".meta.json")


def _load_meta(model_path: Path) -> dict:
    meta_path = _meta_path(model_path)
    if meta_path.is_file():
        return json.loads(meta_path.read_text(encoding="utf-8"))
    return {}


def risk_level_from_probability(prob: float) -> RiskLevel:
    if prob < 0.3:
        return "LOW"
    if prob <= 0.7:
        return "MODERATE"
    return "HIGH"


def glaucoma_prediction_from_probability(prob: float) -> GlaucomaPrediction:
    p = max(0.0, min(1.0, float(prob)))
    risk = risk_level_from_probability(p)
    label = "glaucoma" if p >= 0.5 else "normal"
    confidence = max(p, 1.0 - p)

    if risk == "LOW":
        grade, grade_label = 0, "normal"
    elif risk == "MODERATE":
        grade, grade_label = 1, "suspect"
    else:
        grade, grade_label = 2, "glaucoma"

    return GlaucomaPrediction(
        probability=p,
        label=label,
        glaucoma_grade=grade,
        grade_label=grade_label,
        confidence=confidence,
        risk_level=risk,
    )


def prediction_to_result(
    pred: GlaucomaPrediction,
    *,
    model_used: str = "cnn(efficientnet_b4_glaucoma)",
    ontology_passed: bool = True,
    decision_mode: str = "legacy",
    audit_trail: dict | None = None,
    cup_disc_ratio: dict | CupDiscRatioDetail | None = None,
    heatmap: dict | GlaucomaHeatmap | None = None,
    decision: str | None = None,
) -> GlaucomaResult:
    referral = (
        "immediate"
        if pred.risk_level == "HIGH"
        else "routine"
        if pred.risk_level == "MODERATE"
        else "none"
    )
    icd = "H40.1" if pred.glaucoma_grade >= 1 else ""
    audit = audit_trail or {}
    cdr_out: CupDiscRatioDetail | None = None
    if cup_disc_ratio is not None:
        if isinstance(cup_disc_ratio, CupDiscRatioDetail):
            cdr_out = cup_disc_ratio
        else:
            cdr_out = CupDiscRatioDetail(**cup_disc_ratio)
    hm_out: GlaucomaHeatmap | None = None
    if heatmap is not None:
        if isinstance(heatmap, GlaucomaHeatmap):
            hm_out = heatmap
        else:
            lesions = [
                GlaucomaLesionAnnotation(**a)
                if isinstance(a, dict)
                else a
                for a in heatmap.get("lesion_annotations", [])
            ]
            hm_out = GlaucomaHeatmap(
                image_base64=heatmap.get("image_base64", ""),
                resolution=heatmap.get("resolution", "original"),
                lesion_annotations=lesions,
                hotspot_regions=list(heatmap.get("hotspot_regions") or []),
                gradcam_version=heatmap.get("gradcam_version"),
                heatmap_error=heatmap.get("heatmap_error"),
            )
    resolved_decision = decision or audit.get("decision")
    return GlaucomaResult(
        glaucoma_grade=pred.glaucoma_grade,
        grade_label=pred.grade_label,
        label=pred.label,
        probability=pred.probability,
        confidence=pred.confidence,
        risk_level=pred.risk_level,
        cup_disc_ratio=cdr_out,
        heatmap=hm_out,
        icd10_code=icd or "H40.0",
        severity=pred.grade_label,
        referral_urgency=referral,
        model_used=model_used,
        decision_mode=decision_mode,
        ontology_passed=ontology_passed,
        decision=resolved_decision,
        audit_trail=audit,
    )


class GlaucomaOnnxBackend:
    def __init__(self, model_path: Path | None = None) -> None:
        self._path = model_path or get_glaucoma_model_path()
        self._sess = None
        self._meta: dict | None = None

    def _load_meta(self) -> dict:
        if self._meta is None:
            self._meta = _load_meta(self._path)
        return self._meta

    def image_size(self) -> int:
        meta = self._load_meta()
        try:
            return int(meta.get("image_size") or DEFAULT_IMAGE_SIZE)
        except (TypeError, ValueError):
            return DEFAULT_IMAGE_SIZE

    def preprocess_mode(self) -> str:
        meta = self._load_meta()
        return resolve_preprocess_mode(str(meta.get("preprocess") or "clahe"))

    def model_label(self) -> str:
        return str(self._load_meta().get("arch") or "efficientnet_b4_glaucoma")

    def _ensure_session(self) -> None:
        if self._sess is not None:
            return
        if not self._path.is_file():
            raise FileNotFoundError(f"Glaucoma ONNX not found: {self._path}")
        import onnxruntime as ort

        self._sess = ort.InferenceSession(
            str(self._path),
            providers=["CPUExecutionProvider"],
        )

    def predict_sync(self, image_bytes: bytes) -> GlaucomaPrediction:
        self._ensure_session()
        tensor = preprocess_fundus_bytes(
            image_bytes,
            image_size=self.image_size(),
            preprocess_mode=self.preprocess_mode(),
        )
        inp = self._sess.get_inputs()[0].name
        out = self._sess.run(None, {inp: tensor.numpy()})[0]
        logit = float(out.reshape(-1)[0])
        prob = 1.0 / (1.0 + math.exp(-logit))
        return glaucoma_prediction_from_probability(prob)


_backend: GlaucomaOnnxBackend | None = None


def get_glaucoma_backend() -> GlaucomaOnnxBackend:
    global _backend
    if _backend is None:
        _backend = GlaucomaOnnxBackend()
    return _backend


async def predict_glaucoma_from_image_bytes(image_bytes: bytes) -> GlaucomaPrediction:
    import asyncio

    backend = get_glaucoma_backend()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, backend.predict_sync, image_bytes)
