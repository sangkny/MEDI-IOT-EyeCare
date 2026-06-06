"""근시(Myopia) CNN 추론 — retinal_myopia_v1 ONNX."""
from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from schemas.integrated_diagnosis import MyopiaHeatmap, MyopiaLesionAnnotation, MyopiaResult
from services.retinal_cnn import (
    DEFAULT_IMAGE_SIZE,
    preprocess_fundus_bytes,
    resolve_preprocess_mode,
)

log = logging.getLogger("services.myopia_cnn")

RiskLevel = Literal["LOW", "MODERATE", "HIGH"]
VisionImpact = Literal["minimal", "moderate", "severe"]
MYOPIA_GRADE_LABELS = ("normal", "mild", "moderate", "high")
AXIAL_LENGTH_BY_GRADE = {0: 23.5, 1: 25.0, 2: 26.5, 3: 28.0}


@dataclass(frozen=True)
class MyopiaPrediction:
    probability: float
    label: str
    myopia_grade: int
    grade_label: str
    confidence: float
    risk_level: RiskLevel
    axial_length_estimate: float
    pathological: bool
    vision_impact: VisionImpact
    icd10_code: str
    referral_urgency: str


def get_myopia_model_path() -> Path:
    root = Path((os.getenv("MEDI_APP_ROOT") or "/app").strip())
    raw = (os.getenv("MEDI_MYOPIA_MODEL_PATH") or "models/retinal_myopia_v1.onnx").strip()
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


def referral_from_risk(risk: RiskLevel, prob: float) -> str:
    if risk == "HIGH":
        return "immediate" if prob >= 0.85 else "urgent"
    if risk == "MODERATE":
        return "routine"
    return "none"


def myopia_prediction_from_probability(prob: float) -> MyopiaPrediction:
    p = max(0.0, min(1.0, float(prob)))
    risk = risk_level_from_probability(p)
    label = "myopia" if p >= 0.5 else "normal"
    confidence = max(p, 1.0 - p)

    if p < 0.3:
        grade = 0
        vision_impact: VisionImpact = "minimal"
        icd10 = ""
        pathological = False
    elif p <= 0.5:
        grade = 1
        vision_impact = "minimal"
        icd10 = "H52.1"
        pathological = False
    elif p <= 0.7:
        grade = 2
        vision_impact = "moderate"
        icd10 = "H52.1"
        pathological = False
    else:
        grade = 3
        vision_impact = "severe"
        icd10 = "H44.2"
        pathological = True

    grade_label = MYOPIA_GRADE_LABELS[grade]
    axial = AXIAL_LENGTH_BY_GRADE[grade]

    return MyopiaPrediction(
        probability=p,
        label=label,
        myopia_grade=grade,
        grade_label=grade_label,
        confidence=confidence,
        risk_level=risk,
        axial_length_estimate=axial,
        pathological=pathological,
        vision_impact=vision_impact,
        icd10_code=icd10,
        referral_urgency=referral_from_risk(risk, p),
    )


def prediction_to_result(
    pred: MyopiaPrediction,
    *,
    model_used: str = "cnn(efficientnet_b4_myopia)",
    ontology_passed: bool = True,
    decision_mode: str = "legacy",
    audit_trail: dict | None = None,
    heatmap: dict | MyopiaHeatmap | None = None,
    decision: str | None = None,
) -> MyopiaResult:
    audit = audit_trail or {}
    hm_out: MyopiaHeatmap | None = None
    if heatmap is not None:
        if isinstance(heatmap, MyopiaHeatmap):
            hm_out = heatmap
        else:
            lesions = [
                MyopiaLesionAnnotation(**a) if isinstance(a, dict) else a
                for a in heatmap.get("lesion_annotations", [])
            ]
            hm_out = MyopiaHeatmap(
                image_base64=heatmap.get("image_base64", ""),
                resolution=heatmap.get("resolution", "original"),
                lesion_annotations=lesions,
                hotspot_regions=list(heatmap.get("hotspot_regions") or []),
                gradcam_version=heatmap.get("gradcam_version"),
                heatmap_error=heatmap.get("heatmap_error"),
            )
    resolved_decision = decision or audit.get("decision")
    return MyopiaResult(
        myopia_grade=pred.myopia_grade,
        grade_label=pred.grade_label,
        label=pred.label,
        probability=pred.probability,
        confidence=pred.confidence,
        risk_level=pred.risk_level,
        axial_length_estimate=pred.axial_length_estimate,
        pathological=pred.pathological,
        vision_impact=pred.vision_impact,
        icd10_code=pred.icd10_code or "H52.1",
        referral_urgency=pred.referral_urgency,
        severity=pred.grade_label,
        model_used=model_used,
        decision_mode=decision_mode,
        ontology_passed=ontology_passed,
        decision=resolved_decision,
        audit_trail=audit,
        heatmap=hm_out,
    )


class MyopiaOnnxBackend:
    def __init__(self, model_path: Path | None = None) -> None:
        self._path = model_path or get_myopia_model_path()
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
        return str(self._load_meta().get("arch") or "efficientnet_b4_myopia")

    def _ensure_session(self) -> None:
        if self._sess is not None:
            return
        if not self._path.is_file():
            raise FileNotFoundError(f"Myopia ONNX not found: {self._path}")
        import onnxruntime as ort

        self._sess = ort.InferenceSession(
            str(self._path),
            providers=["CPUExecutionProvider"],
        )

    def predict_sync(self, image_bytes: bytes) -> MyopiaPrediction:
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
        return myopia_prediction_from_probability(prob)


_backend: MyopiaOnnxBackend | None = None


def get_myopia_backend() -> MyopiaOnnxBackend:
    global _backend
    if _backend is None:
        _backend = MyopiaOnnxBackend()
    return _backend


async def predict_myopia_from_image_bytes(image_bytes: bytes) -> MyopiaPrediction:
    import asyncio

    backend = get_myopia_backend()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, backend.predict_sync, image_bytes)
