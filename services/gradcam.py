"""Grad-CAM — CNN 안저 관심 영역 시각화 (설명 가능 AI)."""
from __future__ import annotations

import asyncio
import base64
import io
import logging
from pathlib import Path

import numpy as np

from services.inference_router import load_inference_config
from services.retinal_cnn import (
    build_dr_classifier,
    preprocess_fundus_array,
    resolve_cnn_arch,
    resolve_preprocess_mode,
)

log = logging.getLogger("services.gradcam")


class GradCAMVisualizer:
    """EfficientNet features 마지막 conv에 Grad-CAM 적용 → PNG base64."""

    def __init__(self, config=None) -> None:
        self._config = config or load_inference_config()
        self._model = None
        self._device = None
        self._target_layer = None

    def _meta_path(self) -> Path:
        p = self._config.cnn_model_path
        if p.suffix in {".onnx", ".pt"}:
            return p.with_name(p.stem + ".meta.json")
        return p.parent / "retinal_v1.meta.json"

    def _load_meta(self) -> dict:
        mp = self._meta_path()
        if mp.is_file():
            import json

            return json.loads(mp.read_text(encoding="utf-8"))
        return {}

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        import torch

        meta = self._load_meta()
        arch = resolve_cnn_arch(str(meta.get("arch") or self._config.cnn_arch))
        model, _ = build_dr_classifier(arch=arch, pretrained=False)
        device = torch.device(
            self._config.cnn_device if self._config.cnn_device == "cuda" else "cpu"
        )
        model.to(device)
        model.eval()
        self._model = model
        self._device = device
        feats = model.features
        self._target_layer = feats[-1]

    def _generate_sync(self, image_bytes: bytes) -> str:
        import cv2
        import torch
        from PIL import Image

        self._ensure_model()
        meta = self._load_meta()
        size = int(meta.get("input_size", [224, 224])[0] if meta.get("input_size") else 224)
        pm = resolve_preprocess_mode(str(meta.get("preprocess") or ""))

        pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        orig = np.array(pil)
        arr = preprocess_fundus_array(orig, mode=pm)
        resized = Image.fromarray(arr).resize((size, size))
        tensor = torch.from_numpy(np.array(resized)).permute(2, 0, 1).float() / 255.0
        tensor = tensor.unsqueeze(0).to(self._device)
        tensor.requires_grad_(True)

        activations: list[torch.Tensor] = []
        gradients: list[torch.Tensor] = []

        def fwd_hook(_module, _inp, out):
            activations.append(out)

        def bwd_hook(_module, _gin, grad_out):
            gradients.append(grad_out[0])

        h1 = self._target_layer.register_forward_hook(fwd_hook)
        h2 = self._target_layer.register_full_backward_hook(bwd_hook)

        try:
            logits = self._model(tensor)
            target_class = int(logits.argmax(dim=1).item())
            self._model.zero_grad(set_to_none=True)
            logits[0, target_class].backward()

            acts = activations[-1].detach()[0]
            grads = gradients[-1].detach()[0]
            weights = grads.mean(dim=(1, 2))
            cam = torch.zeros(acts.shape[1:], device=acts.device)
            for i, w in enumerate(weights):
                cam += w * acts[i]
            cam = torch.relu(cam)
            cam_np = cam.cpu().numpy()
            cam_np = (cam_np - cam_np.min()) / (cam_np.max() - cam_np.min() + 1e-8)
            heat = cv2.resize(cam_np, (orig.shape[1], orig.shape[0]))
            heat_u8 = (heat * 255).astype(np.uint8)
            heat_color = cv2.applyColorMap(heat_u8, cv2.COLORMAP_JET)
            heat_rgb = cv2.cvtColor(heat_color, cv2.COLOR_BGR2RGB)
            overlay = (0.55 * orig.astype(np.float32) + 0.45 * heat_rgb.astype(np.float32))
            overlay = np.clip(overlay, 0, 255).astype(np.uint8)

            buf = io.BytesIO()
            Image.fromarray(overlay).save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode("ascii")
        finally:
            h1.remove()
            h2.remove()

    async def generate_heatmap(
        self,
        image_bytes: bytes,
        model=None,
        target_layer=None,
    ) -> str:
        """히트맵 PNG → base64 (model/target_layer 인자는 API 호환용, 내부에서 자체 로드)."""
        del model, target_layer
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._generate_sync, image_bytes)
