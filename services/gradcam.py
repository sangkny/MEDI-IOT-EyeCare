"""Grad-CAM++ — CNN 안저 관심 영역 + DR 병변 레이블 (설명 가능 AI)."""
from __future__ import annotations

import asyncio
import base64
import io
import logging
from pathlib import Path
from typing import Any

import numpy as np

from services.inference_router import load_inference_config
from services.retinal_cnn import (
    build_dr_classifier,
    preprocess_fundus_array,
    resolve_cnn_arch,
    resolve_preprocess_mode,
)

log = logging.getLogger("services.gradcam")

DR_LESION_LABELS: dict[int, list[str]] = {
    0: [],
    1: ["미세혈관류(MA)"],
    2: ["출혈(HE)", "경성삼출물(EX)"],
    3: ["면화반(CWS)", "정맥확장(VB)"],
    4: ["신생혈관(NV)", "유리체출혈(VH)"],
}


def _encode_png_b64(rgb: np.ndarray) -> str:
    from PIL import Image

    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _load_state_dict(model: Any, ckpt: object, arch: str) -> None:
    if isinstance(ckpt, dict) and "model_state" in ckpt:
        model.load_state_dict(ckpt["model_state"])
    elif isinstance(ckpt, dict) and "state_dict" in ckpt:
        if resolve_cnn_arch(str(ckpt.get("arch", arch))) != arch:
            raise RuntimeError(
                f"GradCAM arch mismatch: meta={arch!r} ckpt={ckpt.get('arch')!r}"
            )
        model.load_state_dict(ckpt["state_dict"])
    elif isinstance(ckpt, dict) and ckpt and all(
        isinstance(v, __import__("torch").Tensor) for v in ckpt.values()
    ):
        model.load_state_dict(ckpt)
    elif ckpt is not None and not isinstance(ckpt, dict):
        model.load_state_dict(ckpt)  # type: ignore[arg-type]
    else:
        raise RuntimeError("GradCAM cannot load weights from checkpoint")


def _resolve_target_layer(model: Any) -> Any:
    """EfficientNet / SE / 일반 CNN — GradCAM hook 대상 Conv2d."""
    import torch.nn as nn

    if hasattr(model, "features"):
        last = model.features[-1]
        if isinstance(last, nn.Conv2d):
            return last
        if isinstance(last, nn.Sequential):
            for sub in reversed(list(last)):
                if isinstance(sub, nn.Conv2d):
                    return sub
        for name, module in reversed(list(model.named_modules())):
            if name.startswith("features") and isinstance(module, nn.Conv2d):
                return module

    for module in reversed(list(model.modules())):
        if isinstance(module, nn.Conv2d):
            return module
    return GradCAMPlusPlus._get_last_conv(model)


def _resolve_pt_path(config_path: Path, meta: dict) -> Path:
    """ONNX 추론 경로 → GradCAM용 .pt 체크포인트."""
    models_dir = config_path.parent
    pt_name = str(meta.get("pt") or "").strip()
    if pt_name:
        candidate = models_dir / pt_name
        if candidate.is_file():
            return candidate
    sibling = config_path.with_suffix(".pt")
    if sibling.is_file():
        return sibling
    arch = str(meta.get("arch") or "")
    if arch:
        for pt in sorted(models_dir.glob("retinal_v*.pt"), reverse=True):
            mp = pt.with_name(pt.stem + ".meta.json")
            if mp.is_file():
                import json

                m = json.loads(mp.read_text(encoding="utf-8"))
                if str(m.get("arch") or "") == arch:
                    return pt
    raise FileNotFoundError(
        f"GradCAM PT checkpoint not found for {config_path.name} "
        f"(expected {pt_name or sibling.name}). "
        "Copy .pt alongside .onnx from GPU training output."
    )


class GradCAMPlusPlus:
    """GradCAM++ — 병변 위치 정밀도 향상."""

    def __init__(self, model: Any, target_layer: Any = None) -> None:
        import torch.nn as nn

        self.model = model
        self.target_layer = target_layer or _resolve_target_layer(model)
        if self.target_layer is None:
            raise RuntimeError("GradCAM++: no Conv2d target layer found")
        self.gradients: list[Any] = []
        self.activations: list[Any] = []

    @staticmethod
    def _get_last_conv(model: Any) -> Any:
        import torch.nn as nn

        for module in reversed(list(model.modules())):
            if isinstance(module, nn.Conv2d):
                return module
        return None

    def _register_hooks(self) -> list[Any]:
        import torch

        self.gradients.clear()
        self.activations.clear()

        def fwd_hook(_module, _inp, out):
            self.activations.append(out)

        def bwd_hook(_module, _gin, grad_out):
            self.gradients.append(grad_out[0])

        return [
            self.target_layer.register_forward_hook(fwd_hook),
            self.target_layer.register_full_backward_hook(bwd_hook),
        ]

    def generate(
        self,
        image_tensor: Any,
        target_class: int | None = None,
    ) -> tuple[np.ndarray, int]:
        import torch
        import torch.nn.functional as F

        self.model.eval()
        hooks = self._register_hooks()
        try:
            output = self.model(image_tensor)
            if target_class is None:
                target_class = int(output.argmax(dim=1).item())
            else:
                target_class = int(target_class)

            self.model.zero_grad(set_to_none=True)
            score = output[0, target_class]
            score.backward()

            grads = self.gradients[-1][0]
            acts = self.activations[-1][0]

            grads_sq = grads**2
            grads_cub = grads**3
            denom = 2.0 * grads_sq + (acts * grads_cub).sum(dim=(1, 2), keepdim=True)
            denom = torch.where(denom != 0.0, denom, torch.ones_like(denom))
            alpha = grads_sq / denom

            weights = (alpha * F.relu(grads)).sum(dim=(1, 2))
            cam = (weights[:, None, None] * acts).sum(dim=0)
            cam = F.relu(cam)
            h, w = image_tensor.shape[2], image_tensor.shape[3]
            cam = cam.unsqueeze(0).unsqueeze(0)
            cam = F.interpolate(cam, size=(h, w), mode="bilinear", align_corners=False)
            cam_np = cam.squeeze().detach().cpu().numpy()
            cam_np = (cam_np - cam_np.min()) / (cam_np.max() - cam_np.min() + 1e-8)
            return cam_np, target_class
        finally:
            for h in hooks:
                h.remove()


def generate_annotated_heatmap(
    image_bytes: bytes,
    dr_grade: int,
    *,
    visualizer: "GradCAMVisualizer | None" = None,
    lang: str = "ko",
) -> dict[str, Any]:
    """
    GradCAM++ 히트맵 + 병변 레이블·핫스팟.

    반환: heatmap_base64, lesion_labels, attention_score, hotspot_regions, gradcam_version
    """
    del lang
    try:
        import cv2
        import torch
        from PIL import Image

        viz = visualizer or GradCAMVisualizer()
        viz._ensure_model()
        meta = viz._load_meta()
        size = int(meta.get("image_size") or meta.get("input_size") or 224)
        pm = resolve_preprocess_mode(str(meta.get("preprocess") or ""))

        pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        orig = np.array(pil)
        arr = preprocess_fundus_array(orig, mode=pm)
        resized = Image.fromarray(arr).resize((size, size))
        tensor = torch.from_numpy(np.array(resized)).permute(2, 0, 1).float() / 255.0
        tensor = tensor.unsqueeze(0).to(viz._device)
        tensor.requires_grad_(True)

        grade = max(0, min(4, int(dr_grade)))
        gpp = GradCAMPlusPlus(viz._model, target_layer=viz._target_layer)
        cam, target_cls = gpp.generate(tensor, target_class=grade)

        heat_u8 = (cam * 255).astype(np.uint8)
        heat_color = cv2.applyColorMap(heat_u8, cv2.COLORMAP_JET)
        heat_rgb = cv2.cvtColor(heat_color, cv2.COLOR_BGR2RGB)
        heat_resized = cv2.resize(heat_rgb, (orig.shape[1], orig.shape[0]))
        overlay = (0.6 * orig.astype(np.float32) + 0.4 * heat_resized.astype(np.float32))
        overlay = np.clip(overlay, 0, 255).astype(np.uint8)

        threshold = float(cam.max()) * 0.8
        hotspots_y, hotspots_x = np.where(cam > threshold)
        hotspot_regions: list[dict[str, float]] = []
        for x, y in zip(hotspots_x[:10], hotspots_y[:10]):
            hotspot_regions.append(
                {
                    "x": float(x / max(cam.shape[1], 1)),
                    "y": float(y / max(cam.shape[0], 1)),
                    "intensity": float(cam[y, x]),
                }
            )

        return {
            "heatmap_base64": _encode_png_b64(overlay),
            "lesion_labels": DR_LESION_LABELS.get(grade, DR_LESION_LABELS.get(target_cls, [])),
            "attention_score": float(cam.max()),
            "hotspot_regions": hotspot_regions,
            "gradcam_version": "gradcam++",
            "gradcam_target_class": target_cls,
            "heatmap_error": None,
        }
    except Exception as exc:
        log.exception("GradCAM++ failed")
        return {
            "heatmap_base64": "",
            "lesion_labels": DR_LESION_LABELS.get(max(0, min(4, int(dr_grade))), []),
            "attention_score": None,
            "hotspot_regions": [],
            "gradcam_version": None,
            "heatmap_error": str(exc)[:500],
        }


class GradCAMVisualizer:
    """EfficientNet features 마지막 conv — GradCAM++ 적용."""

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
        cfg_path = self._config.cnn_model_path
        pt_path = _resolve_pt_path(cfg_path, meta)
        try:
            ckpt = torch.load(pt_path, map_location="cpu", weights_only=False)
        except TypeError:
            ckpt = torch.load(pt_path, map_location="cpu")
        if isinstance(ckpt, dict) and ckpt.get("arch"):
            arch = resolve_cnn_arch(str(ckpt["arch"]))
        model, arch_key = build_dr_classifier(arch=arch, pretrained=False)
        _load_state_dict(model, ckpt, arch_key)
        device = torch.device(
            self._config.cnn_device if self._config.cnn_device == "cuda" else "cpu"
        )
        model.to(device)
        model.eval()
        self._model = model
        self._device = device
        self._target_layer = _resolve_target_layer(model)
        log.info("GradCAM loaded PT weights from %s (arch=%s)", pt_path.name, arch_key)

    def _generate_sync(self, image_bytes: bytes, dr_grade: int | None = None) -> str:
        grade = 0 if dr_grade is None else int(dr_grade)
        return generate_annotated_heatmap(
            image_bytes, grade, visualizer=self
        )["heatmap_base64"]

    async def generate_heatmap(
        self,
        image_bytes: bytes,
        model=None,
        target_layer=None,
        *,
        dr_grade: int | None = None,
    ) -> str:
        del model, target_layer
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: self._generate_sync(image_bytes, dr_grade)
        )

    async def generate_annotated(
        self,
        image_bytes: bytes,
        dr_grade: int,
    ) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: generate_annotated_heatmap(image_bytes, dr_grade, visualizer=self),
        )
