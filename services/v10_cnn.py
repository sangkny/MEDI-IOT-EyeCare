"""v10 통합 멀티태스크 ONNX — 5질환 단일 추론."""
from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass
from pathlib import Path

from services.amd_cnn import AMDPrediction, amd_prediction_from_probability
from services.glaucoma_cnn import GlaucomaPrediction, glaucoma_prediction_from_probability
from services.myopia_cnn import MyopiaPrediction, myopia_prediction_from_probability
from services.multidisease_cnn import MultidiseasePrediction
from services.retinal_cnn import (
    DEFAULT_IMAGE_SIZE,
    DrPrediction,
    dr_prediction_from_logits,
    preprocess_fundus_bytes,
    resolve_preprocess_mode,
)
from training.make_manifest import MULTIDISEASE_TRAIN_CLASSES

log = logging.getLogger("services.v10_cnn")


@dataclass(frozen=True)
class V10Prediction:
    dr: DrPrediction
    glaucoma: GlaucomaPrediction
    amd: AMDPrediction
    myopia: MyopiaPrediction
    multidisease: MultidiseasePrediction


def _v10_enabled() -> bool:
    flag = (os.getenv("MEDI_V10_ENABLED") or "auto").strip().lower()
    if flag in ("0", "false", "off", "no"):
        return False
    if flag in ("1", "true", "on", "yes"):
        return True
    return get_v10_model_path().is_file()


def get_v10_model_path() -> Path:
    root = Path((os.getenv("MEDI_APP_ROOT") or "/app").strip())
    raw = (os.getenv("MEDI_V10_MODEL_PATH") or "models/retinal_v10.onnx").strip()
    path = Path(raw) if Path(raw).is_absolute() else root / raw
    if path.suffix != ".onnx":
        onnx_alt = path.with_suffix(".onnx")
        if onnx_alt.is_file():
            return onnx_alt
    return path


def is_v10_available() -> bool:
    return _v10_enabled()


def _meta_path(model_path: Path) -> Path:
    return model_path.with_name(model_path.stem + ".meta.json")


def _load_meta(model_path: Path) -> dict:
    meta_path = _meta_path(model_path)
    if meta_path.is_file():
        return json.loads(meta_path.read_text(encoding="utf-8"))
    return {}


class V10OnnxBackend:
    def __init__(self, model_path: Path | None = None) -> None:
        self._path = model_path or get_v10_model_path()
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
        return resolve_preprocess_mode(str(meta.get("preprocess") or "none"))

    def model_label(self) -> str:
        return str(self._load_meta().get("arch") or "efficientnet_b4_v10")

    def class_names(self) -> tuple[str, ...]:
        meta = self._load_meta()
        raw = meta.get("label_classes") or list(MULTIDISEASE_TRAIN_CLASSES)
        return tuple(str(x) for x in raw)

    def _ensure_session(self) -> None:
        if self._sess is not None:
            return
        if not self._path.is_file():
            raise FileNotFoundError(f"v10 ONNX not found: {self._path}")
        import onnxruntime as ort

        self._sess = ort.InferenceSession(
            str(self._path),
            providers=["CPUExecutionProvider"],
        )

    def predict_sync(self, image_bytes: bytes) -> V10Prediction:
        self._ensure_session()
        tensor = preprocess_fundus_bytes(
            image_bytes,
            image_size=self.image_size(),
            preprocess_mode=self.preprocess_mode(),
        )
        inp = self._sess.get_inputs()[0].name
        dr_out, gl_out, amd_out, myo_out, multi_out = self._sess.run(
            None,
            {inp: tensor.numpy()},
        )
        dr_pred = dr_prediction_from_logits(dr_out)
        gl_logit = float(gl_out.reshape(-1)[0])
        amd_logit = float(amd_out.reshape(-1)[0])
        myo_logit = float(myo_out.reshape(-1)[0])
        gl_prob = 1.0 / (1.0 + math.exp(-gl_logit))
        amd_prob = 1.0 / (1.0 + math.exp(-amd_logit))
        myo_prob = 1.0 / (1.0 + math.exp(-myo_logit))

        names = self.class_names()
        multi_logits = multi_out.reshape(-1)
        multi_probs = {
            name: 1.0 / (1.0 + math.exp(-float(multi_logits[i])))
            for i, name in enumerate(names)
            if i < len(multi_logits)
        }

        return V10Prediction(
            dr=dr_pred,
            glaucoma=glaucoma_prediction_from_probability(gl_prob),
            amd=amd_prediction_from_probability(amd_prob),
            myopia=myopia_prediction_from_probability(myo_prob),
            multidisease=MultidiseasePrediction(
                probabilities=multi_probs,
                class_names=names,
            ),
        )


_backend: V10OnnxBackend | None = None


def get_v10_backend() -> V10OnnxBackend:
    global _backend
    if _backend is None:
        _backend = V10OnnxBackend()
    return _backend


async def predict_v10_from_image_bytes(image_bytes: bytes) -> V10Prediction:
    import asyncio

    backend = get_v10_backend()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, backend.predict_sync, image_bytes)
