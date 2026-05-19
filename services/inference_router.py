"""이미지 추론 라우터 — LLM VISION / Retinal CNN / ensemble (D R4-ML D3).

환경 변수:
    MEDI_INFERENCE_BACKEND   llm | cnn | ensemble  (기본 llm)
    MEDI_CNN_MODEL_PATH      .onnx 또는 .pt (기본 models/retinal_v1.onnx)
    MEDI_CNN_CONFIDENCE_MIN  CNN 단독·ensemble 가중 임계 (기본 0.70)
    MEDI_CNN_ARCH            retinal_cnn.resolve_cnn_arch (meta 없을 때)
    MEDI_CNN_DEVICE          cpu | cuda (torch 추론)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from services.eye_analyzer import AnalysisResult, EyeAnalyzer
from services.retinal_cnn import (
    DEFAULT_IMAGE_SIZE,
    dr_prediction_from_logits,
    dr_prediction_to_parsed,
    preprocess_fundus_bytes,
    resolve_cnn_arch,
)

log = logging.getLogger("services.inference_router")

SEVERITY_RANK: dict[str, int] = {
    "normal": 0,
    "mild": 1,
    "moderate": 2,
    "severe": 3,
    "critical": 4,
}


@dataclass(frozen=True)
class InferenceConfig:
    backend: str
    cnn_model_path: Path
    cnn_confidence_min: float
    cnn_arch: str
    cnn_device: str

    @property
    def is_cnn(self) -> bool:
        return self.backend in {"cnn", "ensemble"}

    @property
    def is_ensemble(self) -> bool:
        return self.backend == "ensemble"


def load_inference_config() -> InferenceConfig:
    backend = (os.getenv("MEDI_INFERENCE_BACKEND") or "llm").strip().lower()
    if backend not in {"llm", "cnn", "ensemble"}:
        backend = "llm"
    raw_path = (os.getenv("MEDI_CNN_MODEL_PATH") or "models/retinal_v1.onnx").strip()
    path = Path(raw_path)
    if not path.is_absolute():
        path = Path("/app") / path
    try:
        cnn_min = float(os.getenv("MEDI_CNN_CONFIDENCE_MIN", "0.70"))
    except ValueError:
        cnn_min = 0.70
    device = (os.getenv("MEDI_CNN_DEVICE") or "cpu").strip().lower()
    return InferenceConfig(
        backend=backend,
        cnn_model_path=path,
        cnn_confidence_min=cnn_min,
        cnn_arch=resolve_cnn_arch(),
        cnn_device=device,
    )


@runtime_checkable
class InferenceBackend(Protocol):
    async def analyze_image_file(
        self,
        file_path: str,
        exam_type: str = "fundus",
        icd_code: str | None = None,
    ) -> AnalysisResult: ...


class LlmVisionBackend:
    """기존 ``EyeAnalyzer`` VISION + Ontology 경로."""

    def __init__(self, analyzer: EyeAnalyzer | None = None) -> None:
        self._analyzer = analyzer or EyeAnalyzer()

    async def analyze_image_file(
        self,
        file_path: str,
        exam_type: str = "fundus",
        icd_code: str | None = None,
    ) -> AnalysisResult:
        return await self._analyzer.analyze_image_file(
            file_path=file_path,
            exam_type=exam_type,
            icd_code=icd_code,
        )


class CnnRetinalBackend:
    """ONNX Runtime 우선, 없으면 torch no-grad."""

    def __init__(self, config: InferenceConfig) -> None:
        self._config = config
        self._meta: dict[str, Any] | None = None
        self._onnx_sess: Any = None
        self._torch_model: Any = None
        self._arch_label: str = config.cnn_arch

    def _meta_path(self) -> Path:
        p = self._config.cnn_model_path
        if p.suffix in {".onnx", ".pt"}:
            return p.with_name(p.stem + ".meta.json")
        return p.parent / "retinal_v1.meta.json"

    def _load_meta(self) -> dict[str, Any]:
        if self._meta is not None:
            return self._meta
        meta_path = self._meta_path()
        if meta_path.is_file():
            self._meta = json.loads(meta_path.read_text(encoding="utf-8"))
        else:
            self._meta = {}
        arch = self._meta.get("arch") or self._config.cnn_arch
        self._arch_label = resolve_cnn_arch(str(arch))
        return self._meta

    def _image_size(self) -> int:
        meta = self._load_meta()
        try:
            return int(meta.get("image_size") or DEFAULT_IMAGE_SIZE)
        except (TypeError, ValueError):
            return DEFAULT_IMAGE_SIZE

    def _ensure_onnx(self) -> None:
        if self._onnx_sess is not None:
            return
        import onnxruntime as ort

        path = self._config.cnn_model_path
        if path.suffix != ".onnx":
            onnx_alt = path.with_suffix(".onnx")
            if onnx_alt.is_file():
                path = onnx_alt
            else:
                raise FileNotFoundError(f"ONNX model not found: {path}")
        self._onnx_sess = ort.InferenceSession(
            str(path),
            providers=["CPUExecutionProvider"],
        )

    def _ensure_torch(self) -> None:
        if self._torch_model is not None:
            return
        import torch

        from services.retinal_cnn import build_dr_classifier

        path = self._config.cnn_model_path
        if path.suffix == ".onnx":
            pt_alt = path.with_suffix(".pt")
            if pt_alt.is_file():
                path = pt_alt
        if not path.is_file():
            raise FileNotFoundError(f"CNN weights not found: {path}")

        try:
            ckpt = torch.load(path, map_location="cpu", weights_only=False)
        except TypeError:
            ckpt = torch.load(path, map_location="cpu")
        arch = ckpt.get("arch") if isinstance(ckpt, dict) else None
        model, arch_key = build_dr_classifier(
            arch=str(arch) if arch else self._arch_label,
            pretrained=False,
        )
        if isinstance(ckpt, dict) and "state_dict" in ckpt:
            model.load_state_dict(ckpt["state_dict"])
        else:
            model.load_state_dict(ckpt)
        self._arch_label = arch_key
        device = torch.device(self._config.cnn_device)
        model.to(device)
        model.eval()
        self._torch_model = model
        self._torch_device = device

    def _predict_sync(self, image_bytes: bytes) -> Any:
        """DrPrediction 반환."""
        size = self._image_size()
        tensor = preprocess_fundus_bytes(image_bytes, image_size=size)
        path = self._config.cnn_model_path
        use_onnx = path.suffix == ".onnx" or path.with_suffix(".onnx").is_file()

        if use_onnx:
            self._ensure_onnx()
            import numpy as np

            arr = tensor.numpy()
            inp = self._onnx_sess.get_inputs()[0].name
            logits = self._onnx_sess.run(None, {inp: arr})[0]
            return dr_prediction_from_logits(logits[0])
        self._ensure_torch()
        import torch

        device = getattr(self, "_torch_device", torch.device("cpu"))
        with torch.no_grad():
            out = self._torch_model(tensor.to(device))
        return dr_prediction_from_logits(out[0])

    async def analyze_image_file(
        self,
        file_path: str,
        exam_type: str = "fundus",
        icd_code: str | None = None,
    ) -> AnalysisResult:
        if exam_type != "fundus":
            raise ValueError(
                f"CnnRetinalBackend supports fundus only, got {exam_type!r}"
            )
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"이미지 파일 없음: {file_path}")

        image_bytes = path.read_bytes()
        loop = asyncio.get_running_loop()
        try:
            pred = await loop.run_in_executor(None, self._predict_sync, image_bytes)
        except Exception as exc:
            _emit_cnn_metric("error")
            raise

        parsed = dr_prediction_to_parsed(pred)
        model_used = f"cnn({self._arch_label})"
        raw = json.dumps(
            {
                "backend": "cnn",
                "dr_grade": pred.dr_grade,
                "probabilities": list(pred.probabilities),
                "icd_hint": icd_code,
            },
            ensure_ascii=False,
        )

        analyzer = EyeAnalyzer()
        ont = await analyzer._run_ontology_validation(
            parsed, f"{exam_type} cnn inference"
        )
        _emit_cnn_metric("ok", grade=str(pred.dr_grade))

        return AnalysisResult(
            condition=parsed["condition"],
            condition_kr=parsed["condition_kr"],
            severity=parsed["severity"],
            icd10_code=parsed["icd10_code"],
            confidence=parsed["confidence"],
            raw_analysis=raw,
            model_used=model_used,
            ontology_passed=ont.passed,
            ontology_errors=[e.message for e in ont.errors[:5]],
            exam_type=exam_type,
        )


def merge_ensemble_results(
    cnn: AnalysisResult,
    llm: AnalysisResult,
    *,
    cnn_confidence_min: float,
) -> AnalysisResult:
    """ICD 합의 우선, 불일치 시 CNN 신뢰도가 임계 이상이면 CNN ICD."""
    icd_cnn = cnn.icd10_code
    icd_llm = llm.icd10_code
    if icd_cnn == icd_llm:
        icd = icd_cnn
    elif cnn.confidence >= cnn_confidence_min:
        icd = icd_cnn
    else:
        icd = icd_llm

    sev = max(
        (cnn.severity, llm.severity),
        key=lambda s: SEVERITY_RANK.get(s, 0),
    )
    conf = (cnn.confidence + llm.confidence) / 2.0
    ontology_passed = cnn.ontology_passed and llm.ontology_passed
    errors = list(dict.fromkeys(cnn.ontology_errors + llm.ontology_errors))[:5]

    if cnn.confidence >= llm.confidence:
        condition, condition_kr = cnn.condition, cnn.condition_kr
    else:
        condition, condition_kr = llm.condition, llm.condition_kr

    model_used = f"ensemble({cnn.model_used},{llm.model_used})"
    raw = json.dumps(
        {
            "ensemble": True,
            "cnn": {"icd": icd_cnn, "conf": cnn.confidence},
            "llm": {"icd": icd_llm, "conf": llm.confidence},
        },
        ensure_ascii=False,
    )

    return AnalysisResult(
        condition=condition,
        condition_kr=condition_kr,
        severity=sev,
        icd10_code=icd,
        confidence=conf,
        raw_analysis=raw,
        model_used=model_used,
        ontology_passed=ontology_passed,
        ontology_errors=errors,
        exam_type=cnn.exam_type or llm.exam_type,
    )


class EnsembleInferenceBackend:
    def __init__(
        self,
        llm: LlmVisionBackend,
        cnn: CnnRetinalBackend,
        config: InferenceConfig,
    ) -> None:
        self._llm = llm
        self._cnn = cnn
        self._config = config

    async def analyze_image_file(
        self,
        file_path: str,
        exam_type: str = "fundus",
        icd_code: str | None = None,
    ) -> AnalysisResult:
        if exam_type != "fundus":
            return await self._llm.analyze_image_file(file_path, exam_type, icd_code)

        cnn_task = self._cnn.analyze_image_file(file_path, exam_type, icd_code)
        llm_task = self._llm.analyze_image_file(file_path, exam_type, icd_code)
        cnn_res, llm_res = await asyncio.gather(cnn_task, llm_task)
        return merge_ensemble_results(
            cnn_res,
            llm_res,
            cnn_confidence_min=self._config.cnn_confidence_min,
        )


def _emit_cnn_metric(outcome: str, grade: str = "") -> None:
    try:
        from prometheus_client import Counter

        global _CNN_INFERENCE_COUNTER
        try:
            _CNN_INFERENCE_COUNTER
        except NameError:
            _CNN_INFERENCE_COUNTER = Counter(
                "medi_cnn_inference_total",
                "Retinal CNN 추론 결과",
                ["outcome", "grade"],
            )
        _CNN_INFERENCE_COUNTER.labels(outcome=outcome, grade=grade or "na").inc()
    except Exception:
        pass


_router: InferenceBackend | None = None


def get_inference_backend(config: InferenceConfig | None = None) -> InferenceBackend:
    global _router
    cfg = config or load_inference_config()
    if _router is not None and config is None:
        return _router

    llm = LlmVisionBackend()
    if cfg.backend == "llm":
        backend: InferenceBackend = llm
    elif cfg.backend == "cnn":
        backend = CnnRetinalBackend(cfg)
    else:
        backend = EnsembleInferenceBackend(llm, CnnRetinalBackend(cfg), cfg)

    if config is None:
        _router = backend
    log.info(
        "InferenceRouter backend=%s cnn_path=%s arch=%s",
        cfg.backend,
        cfg.cnn_model_path,
        cfg.cnn_arch,
    )
    return backend


async def analyze_image_via_router(
    file_path: str,
    exam_type: str = "fundus",
    icd_code: str | None = None,
) -> AnalysisResult:
    """``api/images`` 분석 진입점."""
    backend = get_inference_backend()
    cfg = load_inference_config()
    if cfg.backend == "cnn" and exam_type != "fundus":
        log.warning("CNN backend requires fundus; falling back to LLM for %s", exam_type)
        return await LlmVisionBackend().analyze_image_file(file_path, exam_type, icd_code)
    try:
        return await backend.analyze_image_file(file_path, exam_type, icd_code)
    except (FileNotFoundError, ValueError) as exc:
        if cfg.backend in {"cnn", "ensemble"} and exam_type == "fundus":
            log.warning("CNN inference failed (%s); LLM fallback", exc)
            return await LlmVisionBackend().analyze_image_file(
                file_path, exam_type, icd_code
            )
        raise


__all__ = [
    "InferenceConfig",
    "InferenceBackend",
    "LlmVisionBackend",
    "CnnRetinalBackend",
    "EnsembleInferenceBackend",
    "load_inference_config",
    "get_inference_backend",
    "analyze_image_via_router",
    "merge_ensemble_results",
]
