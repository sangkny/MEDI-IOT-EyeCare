"""다질환 28-class CNN 추론 — retinal_multidisease_v1 ONNX."""
from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from schemas.integrated_diagnosis import ScreeningFinding, ScreeningResult
from services.retinal_cnn import (
    DEFAULT_IMAGE_SIZE,
    preprocess_fundus_bytes,
    resolve_preprocess_mode,
)
from training.make_manifest import MULTIDISEASE_TRAIN_CLASSES

log = logging.getLogger("services.multidisease_cnn")

RiskLevel = Literal["low", "moderate", "high", "urgent"]
ReferralUrgency = Literal["none", "routine", "immediate"]

DISEASE_MAP: dict[str, tuple[str, str]] = {
    "dr": ("당뇨망막병증", "H36.0"),
    "armd": ("황반변성", "H35.3"),
    "mh": ("미디어헤이즈", "H44.2"),
    "dn": ("드루젠", "H35.3"),
    "mya": ("병적근시", "H44.2"),
    "brvo": ("분지망막정맥폐쇄", "H34.8"),
    "tsln": ("테셀레이션", "H35.4"),
    "erm": ("망막앞막", "H35.3"),
    "ls": ("레이저반흔", "Z98.8"),
    "ms": ("황반반흔", "H35.3"),
    "csr": ("중심장액맥락망막병증", "H35.7"),
    "odc": ("시신경유두함몰", "H47.1"),
    "crvo": ("중심망막정맥폐쇄", "H34.8"),
    "hr": ("고혈압망막병증", "H35.0"),
    "odp": ("시신경유두창백", "H47.2"),
    "ode": ("시신경유두부종", "H47.1"),
    "aion": ("전방허혈시신경병증", "H47.0"),
    "rt": ("망막견인", "H33.4"),
    "rs": ("망막분리증", "H33.7"),
    "crs": ("맥락망막반흔", "H31.0"),
    "edn": ("삼출물", "H35.8"),
    "rpec": ("망막색소상피변화", "H35.7"),
    "mhl": ("황반원공", "H35.3"),
    "rp": ("망막색소변성", "H35.5"),
    "cws": ("면화반", "H35.0"),
    "cb": ("맥락막출혈", "H31.3"),
    "odpm": ("시신경소와황반병증", "H47.1"),
    "prh": ("망막앞출혈", "H35.6"),
}

URGENT_EMERGENCY_DISEASES = frozenset({"crvo", "aion"})
URGENT_PROB_THRESHOLD = 0.7
EMERGENCY_PROB_THRESHOLD = 0.5


@dataclass(frozen=True)
class MultidiseasePrediction:
    probabilities: dict[str, float]
    class_names: tuple[str, ...]


def get_multidisease_threshold() -> float:
    raw = (os.getenv("MEDI_MULTIDISEASE_THRESHOLD") or "0.3").strip()
    try:
        return max(0.0, min(1.0, float(raw)))
    except ValueError:
        return 0.3


def get_multidisease_model_path() -> Path:
    root = Path((os.getenv("MEDI_APP_ROOT") or "/app").strip())
    raw = (os.getenv("MEDI_MULTIDISEASE_MODEL_PATH") or "models/retinal_multidisease_v1.onnx").strip()
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
    p = max(0.0, min(1.0, float(prob)))
    if p >= URGENT_PROB_THRESHOLD:
        return "urgent"
    if p >= 0.5:
        return "high"
    if p >= get_multidisease_threshold():
        return "moderate"
    return "low"


def referral_urgency_from_findings(
    probabilities: dict[str, float],
    *,
    urgent_diseases: list[str],
) -> ReferralUrgency:
    if urgent_diseases:
        return "immediate"
    for code in URGENT_EMERGENCY_DISEASES:
        if probabilities.get(code, 0.0) > EMERGENCY_PROB_THRESHOLD:
            return "immediate"
    threshold = get_multidisease_threshold()
    if any(p >= threshold for p in probabilities.values()):
        return "routine"
    return "none"


def is_normal_screening(probabilities: dict[str, float], *, threshold: float | None = None) -> bool:
    th = threshold if threshold is not None else get_multidisease_threshold()
    return all(p < th for p in probabilities.values())


def prediction_to_screening_result(
    pred: MultidiseasePrediction,
    *,
    model_used: str = "cnn(efficientnet_b4_multidisease)",
    threshold: float | None = None,
    recommendations: list[str] | None = None,
    referral_urgency: str | None = None,
) -> ScreeningResult:
    th = threshold if threshold is not None else get_multidisease_threshold()
    probs = pred.probabilities

    findings: list[ScreeningFinding] = []
    for disease, prob in sorted(probs.items(), key=lambda x: x[1], reverse=True):
        if prob < th:
            continue
        korean, icd10 = DISEASE_MAP.get(disease, (disease, ""))
        findings.append(
            ScreeningFinding(
                disease=disease,
                korean_name=korean,
                probability=round(prob, 4),
                risk_level=risk_level_from_probability(prob),
                icd10=icd10,
            )
        )

    urgent = [
        d for d, p in probs.items()
        if p > URGENT_PROB_THRESHOLD
    ]
    normal = is_normal_screening(probs, threshold=th)
    top = sorted(findings, key=lambda f: f.probability, reverse=True)[:3]
    urgency = referral_urgency or referral_urgency_from_findings(probs, urgent_diseases=urgent)

    recs = list(recommendations or [])
    if urgent:
        recs.append("즉시 안과 전문의 의뢰 — 고확률 소견")
    elif findings:
        recs.append("정기 안과 검진 및 추적 관찰 권장")
    elif normal:
        recs.append("특이 소견 없음 — 정기 검진 유지")

    return ScreeningResult(
        findings=findings,
        urgent_diseases=urgent,
        total_diseases_detected=len(findings),
        recommendations=recs,
        urgent_referral=bool(urgent) or urgency == "immediate",
        priority_diseases=urgent,
        referral_urgency=urgency,
        normal=normal,
        top_findings=top,
        model_used=model_used,
    )


class MultidiseaseOnnxBackend:
    def __init__(self, model_path: Path | None = None) -> None:
        self._path = model_path or get_multidisease_model_path()
        self._sess = None
        self._meta: dict | None = None

    def _load_meta(self) -> dict:
        if self._meta is None:
            self._meta = _load_meta(self._path)
        return self._meta

    def class_names(self) -> tuple[str, ...]:
        meta = self._load_meta()
        raw = meta.get("label_classes") or list(MULTIDISEASE_TRAIN_CLASSES)
        return tuple(str(x) for x in raw)

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
        return str(self._load_meta().get("arch") or "efficientnet_b4_multidisease")

    def _ensure_session(self) -> None:
        if self._sess is not None:
            return
        if not self._path.is_file():
            raise FileNotFoundError(f"Multidisease ONNX not found: {self._path}")
        import onnxruntime as ort

        self._sess = ort.InferenceSession(
            str(self._path),
            providers=["CPUExecutionProvider"],
        )

    def predict_sync(self, image_bytes: bytes) -> MultidiseasePrediction:
        self._ensure_session()
        tensor = preprocess_fundus_bytes(
            image_bytes,
            image_size=self.image_size(),
            preprocess_mode=self.preprocess_mode(),
        )
        inp = self._sess.get_inputs()[0].name
        out = self._sess.run(None, {inp: tensor.numpy()})[0].reshape(-1)
        names = self.class_names()
        if len(out) != len(names):
            log.warning(
                "multidisease output dim=%s class_names=%s — truncating",
                len(out),
                len(names),
            )
        probs: dict[str, float] = {}
        for i, name in enumerate(names):
            if i >= len(out):
                break
            logit = float(out[i])
            prob = 1.0 / (1.0 + math.exp(-logit))
            probs[name] = max(0.0, min(1.0, prob))
        return MultidiseasePrediction(probabilities=probs, class_names=names)


_backend: MultidiseaseOnnxBackend | None = None


def get_multidisease_backend() -> MultidiseaseOnnxBackend:
    global _backend
    if _backend is None:
        _backend = MultidiseaseOnnxBackend()
    return _backend


async def predict_multidisease_from_image_bytes(image_bytes: bytes) -> MultidiseasePrediction:
    import asyncio

    backend = get_multidisease_backend()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, backend.predict_sync, image_bytes)


async def screen_fundus_from_image_bytes(
    image_bytes: bytes,
    *,
    threshold: float | None = None,
    eye: str | None = None,
) -> ScreeningResult:
    """28-class 추론 + 온톨로지 MULTI-SEM 적용."""
    pred = await predict_multidisease_from_image_bytes(image_bytes)
    backend = get_multidisease_backend()
    model_used = f"cnn({backend.model_label()})"
    th = threshold if threshold is not None else get_multidisease_threshold()

    draft = prediction_to_screening_result(pred, model_used=model_used, threshold=th)

    from services.multidisease_ontology import (
        apply_multidisease_ontology,
        build_multidisease_ontology_payload,
    )

    payload = build_multidisease_ontology_payload(
        pred,
        screening=draft,
        model_used=model_used,
        threshold=th,
        eye=eye,
    )
    return await apply_multidisease_ontology(payload, draft)
