"""RETFound ViT-Large attention map 추출 (v8+, GradCAM++ 대안)."""
from __future__ import annotations

import base64
import io
import logging
from pathlib import Path
from typing import Any

import numpy as np

from services.inference_router import load_inference_config

log = logging.getLogger("services.retfound_attention")


def _encode_png_b64(rgb: np.ndarray) -> str:
    from PIL import Image

    buf = io.BytesIO()
    Image.fromarray(rgb.astype(np.uint8)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


class RETFoundAttentionExtractor:
    """
    RETFound ViT-Large attention map 추출.
    ONNX Runtime + ViT patch attention (CLS→patch) 평균.
  v8 ONNX 배포 후 hooks/레이어 이름 튜닝 필요.
    """

    def __init__(self, model_path: str | Path | None = None) -> None:
        cfg = load_inference_config()
        self.model_path = Path(model_path or cfg.cnn_model_path)
        self._session: Any = None

    def _load_session(self) -> Any:
        if self._session is not None:
            return self._session
        import onnxruntime as ort

        if not self.model_path.is_file():
            raise FileNotFoundError(f"RETFound ONNX not found: {self.model_path}")
        self._session = ort.InferenceSession(
            str(self.model_path),
            providers=["CPUExecutionProvider"],
        )
        return self._session

    def extract(self, image_bytes: bytes, *, image_size: int = 224) -> dict:
        """
        반환:
          attention_map_b64, head_weights, top_regions
        """
        from PIL import Image

        from services.retinal_cnn import preprocess_fundus_array, resolve_preprocess_mode

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize(
            (image_size, image_size)
        )
        arr = preprocess_fundus_array(
            np.array(img), mode=resolve_preprocess_mode("clahe")
        )
        x = arr.transpose(2, 0, 1).astype(np.float32)[None, ...]

        sess = self._load_session()
        input_name = sess.get_inputs()[0].name
        logits = sess.run(None, {input_name: x})[0][0]
        probs = np.exp(logits - logits.max())
        probs = probs / probs.sum()
        grade = int(probs.argmax())

        # Placeholder heatmap: uniform until ViT attention weights exported in ONNX
        heat = np.zeros((image_size, image_size), dtype=np.float32)
        heat[image_size // 4 : 3 * image_size // 4, image_size // 4 : 3 * image_size // 4] = 1.0
        heat = (heat - heat.min()) / (heat.max() - heat.min() + 1e-8)
        overlay = (np.array(img) * 0.5 + (heat[..., None] * np.array([255, 0, 0])) * 0.5).astype(
            np.uint8
        )

        top_regions = [
            {"x": 0.5, "y": 0.5, "weight": float(probs.max())},
        ]

        return {
            "dr_grade": grade,
            "confidence": float(probs.max()),
            "attention_map_b64": _encode_png_b64(overlay),
            "head_weights": [1.0],
            "top_regions": top_regions,
            "note": "skeleton: replace with ViT CLS attention when v8 ONNX supports it",
        }
