"""Grad-CAM++ — CNN 안저 관심 영역 + DR 병변 레이블 (설명 가능 AI)."""
from __future__ import annotations

import asyncio
import base64
import io
import logging
from pathlib import Path
from typing import Any

import numpy as np

from services.amd_cnn import get_amd_model_path
from services.glaucoma_cnn import get_glaucoma_model_path
from services.myopia_cnn import get_myopia_model_path
from services.inference_router import load_inference_config
from services.retinal_cnn import (
    build_dr_classifier,
    preprocess_fundus_array,
    resolve_cnn_arch,
    resolve_preprocess_mode,
)

log = logging.getLogger("services.gradcam")

DR_LESION_MAP: dict[int, dict[str, Any]] = {
    0: {
        "labels": [],
        "description_ko": "당뇨망막병증 소견 없음",
        "description_en": "No DR findings",
    },
    1: {
        "labels": ["미세혈관류(MA)"],
        "hotspot_label": "미세혈관류 의심",
        "description_ko": "경미한 당뇨망막병증 — 미세혈관류",
        "description_en": "Mild DR — Microaneurysms",
        "icd10": "E11.311",
    },
    2: {
        "labels": ["출혈(HE)", "경성삼출물(EX)"],
        "hotspot_label": "출혈/삼출 의심",
        "description_ko": "중등도 당뇨망막병증",
        "description_en": "Moderate DR",
        "icd10": "E11.321",
    },
    3: {
        "labels": ["면화반(CWS)", "정맥확장(VB)"],
        "hotspot_label": "면화반/정맥확장",
        "description_ko": "중증 당뇨망막병증",
        "description_en": "Severe DR",
        "icd10": "E11.341",
    },
    4: {
        "labels": ["신생혈관(NV)", "유리체출혈(VH)"],
        "hotspot_label": "신생혈관 의심",
        "description_ko": "증식성 당뇨망막병증",
        "description_en": "Proliferative DR",
        "icd10": "E11.351",
    },
}

# 하위 호환
DR_LESION_LABELS: dict[int, list[str]] = {
    k: v.get("labels", []) for k, v in DR_LESION_MAP.items()
}


def classify_hotspot_region(
    x_norm: float,
    y_norm: float,
    eye_side: str = "unknown",
) -> str:
    """hotspot 위치 → 해부학적 구역 (정규화 좌표 0~1)."""
    del eye_side  # 향후 좌/우안 시신경 위치 보정용
    if 0.35 <= x_norm <= 0.65 and 0.35 <= y_norm <= 0.65:
        return "황반부(macula)"
    if y_norm < 0.33:
        return "상측 혈관궁(superior arcade)"
    if y_norm > 0.67:
        return "하측 혈관궁(inferior arcade)"
    if x_norm < 0.33:
        return "비측(nasal)"
    if x_norm > 0.67:
        return "이측(temporal)"
    return "중간부(mid-periphery)"


def generate_lesion_annotations(
    hotspots: list[dict[str, Any]],
    dr_grade: int,
    attention_score: float,
    eye_side: str = "unknown",
    *,
    lang: str = "ko",
) -> dict[str, Any]:
    """hotspot 위치 + DR 등급 → 병변 주석."""
    grade = max(0, min(4, int(dr_grade)))
    lesion_info = DR_LESION_MAP.get(grade, {})
    desc_key = "description_ko" if lang == "ko" else "description_en"

    annotated_hotspots: list[dict[str, Any]] = []
    for hs in hotspots:
        region = classify_hotspot_region(hs["x"], hs["y"], eye_side)
        annotated_hotspots.append(
            {
                **hs,
                "region": region,
                "lesion_type": lesion_info.get("hotspot_label", "관심 영역"),
            }
        )

    labels = list(lesion_info.get("labels", []))
    if grade > 0 and annotated_hotspots:
        regions = {classify_hotspot_region(h["x"], h["y"], eye_side) for h in hotspots[:5]}
        if any("황반" in r for r in regions) and grade >= 2:
            labels.append("황반부종(DME) 의심")

    high_risk = list(
        dict.fromkeys(
            h["region"]
            for h in annotated_hotspots
            if float(h.get("intensity", 0)) >= 0.80
        )
    )

    return {
        "lesion_labels": labels,
        "lesion_description": lesion_info.get(desc_key, ""),
        "hotspot_regions": annotated_hotspots,
        "attention_score": attention_score,
        "high_risk_regions": high_risk,
    }


def _encode_jpeg_b64(rgb: np.ndarray, *, quality: int = 85) -> str:
    import cv2

    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("JPEG encode failed")
    return base64.b64encode(buf.tobytes()).decode("ascii")


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
    eye_side: str = "unknown",
    overlay_alpha: float = 0.45,
) -> dict[str, Any]:
    """
    GradCAM++ 히트맵 + 병변 레이블·핫스팟 (원본 해상도 오버레이).

    반환: heatmap_base64, lesion_labels, hotspot_regions, cam_resolution 등
    """
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
        orig_w, orig_h = pil.size
        orig_np = np.array(pil)
        proc_np = preprocess_fundus_array(orig_np, mode=pm)
        proc_h, proc_w = proc_np.shape[:2]

        resized = Image.fromarray(proc_np).resize((size, size))
        tensor = torch.from_numpy(np.array(resized)).permute(2, 0, 1).float() / 255.0
        tensor = tensor.unsqueeze(0).to(viz._device)
        tensor.requires_grad_(True)

        grade = max(0, min(4, int(dr_grade)))
        gpp = GradCAMPlusPlus(viz._model, target_layer=viz._target_layer)
        cam, target_cls = gpp.generate(tensor, target_class=grade)

        # CAM → 원본(전처리) 해상도 업스케일
        cam_orig = cv2.resize(cam, (proc_w, proc_h), interpolation=cv2.INTER_CUBIC)
        cam_orig = (cam_orig - cam_orig.min()) / (cam_orig.max() - cam_orig.min() + 1e-8)

        heat_u8 = (cam_orig * 255).astype(np.uint8)
        heat_color = cv2.applyColorMap(heat_u8, cv2.COLORMAP_JET)
        heat_rgb = cv2.cvtColor(heat_color, cv2.COLOR_BGR2RGB)

        base_rgb = proc_np if proc_np.shape[:2] == (proc_h, proc_w) else cv2.resize(
            proc_np, (proc_w, proc_h)
        )
        overlay = (
            (1.0 - overlay_alpha) * base_rgb.astype(np.float32)
            + overlay_alpha * heat_rgb.astype(np.float32)
        )
        overlay = np.clip(overlay, 0, 255).astype(np.uint8)

        threshold = float(cam_orig.max()) * 0.80
        hotspots_y, hotspots_x = np.where(cam_orig > threshold)
        hotspot_regions: list[dict[str, Any]] = []
        for x, y in zip(hotspots_x[:10], hotspots_y[:10]):
            hotspot_regions.append(
                {
                    "x": float(x / max(proc_w, 1)),
                    "y": float(y / max(proc_h, 1)),
                    "intensity": float(cam_orig[y, x]),
                    "x_px": int(x),
                    "y_px": int(y),
                }
            )

        attention_score = float(cam_orig.max())
        lesion_ann = generate_lesion_annotations(
            hotspot_regions,
            grade,
            attention_score,
            eye_side,
            lang=lang,
        )

        return {
            "heatmap_base64": _encode_jpeg_b64(overlay, quality=85),
            "heatmap_width": proc_w,
            "heatmap_height": proc_h,
            "cam_resolution": f"{proc_w}x{proc_h}",
            "orig_width": orig_w,
            "orig_height": orig_h,
            "gradcam_version": "gradcam++",
            "gradcam_target_class": target_cls,
            "heatmap_error": None,
            **lesion_ann,
        }
    except Exception as exc:
        log.exception("GradCAM++ failed")
        grade = max(0, min(4, int(dr_grade)))
        return {
            "heatmap_base64": "",
            "heatmap_width": 0,
            "heatmap_height": 0,
            "cam_resolution": "",
            "lesion_labels": DR_LESION_LABELS.get(grade, []),
            "lesion_description": "",
            "high_risk_regions": [],
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
        *,
        eye_side: str = "unknown",
        lang: str = "ko",
    ) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: generate_annotated_heatmap(
                image_bytes,
                dr_grade,
                visualizer=self,
                eye_side=eye_side,
                lang=lang,
            ),
        )


# ════════════════════════════════════════════════════════════
# Glaucoma GradCAM++ (binary EfficientNet-B4)
# ════════════════════════════════════════════════════════════

GLAUCOMA_LESION_TYPES: list[dict[str, Any]] = [
    {
        "type": "optic_disc_enlargement",
        "label_ko": "시신경유두 확대",
        "region": "center",
        "min_prob": 0.7,
    },
    {
        "type": "cup_disc_asymmetry",
        "label_ko": "좌우 비대칭",
        "region": "nasal",
        "min_prob": 0.55,
    },
    {
        "type": "peripapillary_atrophy",
        "label_ko": "시신경 주위 위축",
        "region": "peripapillary",
        "min_prob": 0.6,
    },
    {
        "type": "nerve_fiber_defect",
        "label_ko": "신경섬유층 결손",
        "region": "superior_arcade",
        "min_prob": 0.65,
    },
]


def _normalize_eye_side(eye: str | None) -> str:
    if not eye:
        return "unknown"
    e = eye.strip().lower()
    if e in ("right", "od", "r"):
        return "right"
    if e in ("left", "os", "l"):
        return "left"
    return "unknown"


def _optic_disc_center(eye_side: str) -> tuple[float, float]:
    """정규화 좌표 — 시신경유두 대략 위치."""
    if eye_side == "left":
        return 0.55, 0.45
    if eye_side == "right":
        return 0.45, 0.45
    return 0.50, 0.45


def generate_glaucoma_lesion_annotations(
    hotspots: list[dict[str, Any]],
    probability: float,
    *,
    eye_side: str = "unknown",
) -> list[dict[str, Any]]:
    """glaucoma 확률 + hotspot → 병변 주석."""
    p = max(0.0, min(1.0, float(probability)))
    annotations: list[dict[str, Any]] = []
    for spec in GLAUCOMA_LESION_TYPES:
        if p < float(spec["min_prob"]):
            continue
        conf = min(0.98, p * (0.85 + 0.1 * (p - spec["min_prob"])))
        region = spec["region"]
        if hotspots:
            hs = max(hotspots, key=lambda h: float(h.get("intensity", 0)))
            region = classify_hotspot_region(hs["x"], hs["y"], eye_side)
        annotations.append(
            {
                "type": spec["type"],
                "confidence": round(conf, 3),
                "region": region,
            }
        )
    if not annotations and p >= 0.5:
        cx, cy = _optic_disc_center(eye_side)
        annotations.append(
            {
                "type": "optic_disc_enlargement",
                "confidence": round(p * 0.9, 3),
                "region": classify_hotspot_region(cx, cy, eye_side),
            }
        )
    return annotations


def _resolve_glaucoma_pt_path(onnx_path: Path, meta: dict) -> Path | None:
    models_dir = onnx_path.parent
    names = [
        str(meta.get("pt") or "").strip(),
        str(meta.get("source_checkpoint") or "").strip(),
        "best.pt",
        onnx_path.stem + ".pt",
    ]
    dirs = [models_dir, models_dir / onnx_path.stem, models_dir / "retinal_glaucoma_v2"]
    for d in dirs:
        for name in names:
            if not name:
                continue
            candidate = d / name
            if candidate.is_file():
                return candidate
    return None


def _build_glaucoma_classifier():
    """이진 녹내장 분류기 (EfficientNet-B4, logit 1)."""
    model, _ = build_dr_classifier(arch="efficientnet_b4", num_classes=1, pretrained=False)
    return model


def _normalize_glaucoma_state_dict(ckpt: object) -> dict:
    """train_glaucoma.py head.* → torchvision EfficientNet classifier.1.* 매핑."""
    import torch

    if isinstance(ckpt, dict) and "model_state" in ckpt:
        sd = ckpt["model_state"]
    elif isinstance(ckpt, dict) and "state_dict" in ckpt:
        sd = ckpt["state_dict"]
    elif isinstance(ckpt, dict) and ckpt and all(
        isinstance(v, torch.Tensor) for v in ckpt.values()
    ):
        sd = ckpt
    else:
        raise RuntimeError("Glaucoma checkpoint has no loadable state_dict")

    out: dict = {}
    for k, v in sd.items():
        key = k[7:] if k.startswith("module.") else k
        key = key.replace("head.", "classifier.1.")
        out[key] = v
    return out


def _load_glaucoma_weights(model: Any, ckpt: object) -> None:
    """Glaucoma PT — head→classifier.1 키 변환 후 로드."""
    sd = _normalize_glaucoma_state_dict(ckpt)
    model.load_state_dict(sd, strict=True)


def _probability_guided_cam(
    proc_h: int,
    proc_w: int,
    probability: float,
    eye_side: str,
) -> np.ndarray:
    """PT 없을 때 optic disc 중심 가우시안 CAM (probability 스케일)."""
    cx_n, cy_n = _optic_disc_center(eye_side)
    cx, cy = int(cx_n * proc_w), int(cy_n * proc_h)
    y_idx, x_idx = np.mgrid[0:proc_h, 0:proc_w]
    sigma = max(proc_w, proc_h) * (0.12 + 0.08 * probability)
    cam = np.exp(
        -((x_idx - cx) ** 2 + (y_idx - cy) ** 2) / (2.0 * sigma**2)
    ).astype(np.float32)
    cam *= 0.5 + 0.5 * probability
    cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-8)
    return cam


def generate_glaucoma_annotated_heatmap(
    image_bytes: bytes,
    probability: float,
    *,
    glaucoma_grade: int = 0,
    eye_side: str = "unknown",
    overlay_alpha: float = 0.45,
) -> dict[str, Any]:
    """Glaucoma GradCAM++ 또는 probability-guided fallback."""
    del glaucoma_grade
    try:
        import cv2
        from PIL import Image

        from services.glaucoma_cnn import _load_meta

        onnx_path = get_glaucoma_model_path()
        meta = _load_meta(onnx_path)
        size = int(meta.get("image_size") or 224)
        pm = resolve_preprocess_mode(str(meta.get("preprocess") or "clahe"))
        eye = _normalize_eye_side(eye_side)

        pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        orig_w, orig_h = pil.size
        orig_np = np.array(pil)
        proc_np = preprocess_fundus_array(orig_np, mode=pm)
        proc_h, proc_w = proc_np.shape[:2]

        cam: np.ndarray | None = None
        gradcam_version = "gradcam++"
        pt_path = _resolve_glaucoma_pt_path(onnx_path, meta)

        if pt_path is not None:
            import torch

            model = _build_glaucoma_classifier()
            try:
                ckpt = torch.load(pt_path, map_location="cpu", weights_only=False)
            except TypeError:
                ckpt = torch.load(pt_path, map_location="cpu")
            _load_glaucoma_weights(model, ckpt)
            device = torch.device("cpu")
            model.to(device).eval()
            target_layer = _resolve_target_layer(model)

            resized = Image.fromarray(proc_np).resize((size, size))
            tensor = torch.from_numpy(np.array(resized)).permute(2, 0, 1).float() / 255.0
            tensor = tensor.unsqueeze(0).to(device)
            tensor.requires_grad_(True)

            gpp = GradCAMPlusPlus(model, target_layer=target_layer)
            cam_small, _ = gpp.generate(tensor, target_class=0)
            cam = cv2.resize(cam_small, (proc_w, proc_h), interpolation=cv2.INTER_CUBIC)
            cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-8)
        else:
            gradcam_version = "probability_guided"
            cam = _probability_guided_cam(proc_h, proc_w, probability, eye)

        heat_u8 = (cam * 255).astype(np.uint8)
        heat_color = cv2.applyColorMap(heat_u8, cv2.COLORMAP_JET)
        heat_rgb = cv2.cvtColor(heat_color, cv2.COLOR_BGR2RGB)
        base_rgb = proc_np
        overlay = (
            (1.0 - overlay_alpha) * base_rgb.astype(np.float32)
            + overlay_alpha * heat_rgb.astype(np.float32)
        )
        overlay = np.clip(overlay, 0, 255).astype(np.uint8)

        threshold = float(cam.max()) * 0.80
        hotspots_y, hotspots_x = np.where(cam > threshold)
        hotspot_regions: list[dict[str, Any]] = []
        for x, y in zip(hotspots_x[:10], hotspots_y[:10]):
            hotspot_regions.append(
                {
                    "x": float(x / max(proc_w, 1)),
                    "y": float(y / max(proc_h, 1)),
                    "intensity": float(cam[y, x]),
                    "x_px": int(x),
                    "y_px": int(y),
                }
            )

        lesion_annotations = generate_glaucoma_lesion_annotations(
            hotspot_regions, probability, eye_side=eye
        )
        hotspot_labels = list(
            dict.fromkeys(
                a["region"] for a in lesion_annotations if a.get("region")
            )
        )
        if "optic_disc" not in hotspot_labels and probability >= 0.5:
            hotspot_labels.insert(0, "optic_disc")
        if probability >= 0.6 and "peripapillary" not in hotspot_labels:
            hotspot_labels.append("peripapillary")

        return {
            "image_base64": _encode_jpeg_b64(overlay, quality=85),
            "resolution": f"{orig_w}x{orig_h}",
            "lesion_annotations": lesion_annotations,
            "hotspot_regions": hotspot_labels,
            "gradcam_version": gradcam_version,
            "heatmap_error": None,
            "heatmap_width": proc_w,
            "heatmap_height": proc_h,
            "cam_resolution": f"{proc_w}x{proc_h}",
            "attention_score": float(cam.max()),
        }
    except Exception as exc:
        log.exception("Glaucoma GradCAM failed")
        return {
            "image_base64": "",
            "resolution": "",
            "lesion_annotations": [],
            "hotspot_regions": [],
            "gradcam_version": None,
            "heatmap_error": str(exc)[:500],
        }


# ════════════════════════════════════════════════════════════
# AMD GradCAM++ (binary EfficientNet-B4, macula-centered)
# ════════════════════════════════════════════════════════════

AMD_LESION_TYPES: list[dict[str, Any]] = [
    {
        "type": "drusen",
        "label_ko": "드루젠",
        "region": "macula",
        "min_prob": 0.35,
    },
    {
        "type": "pigment_epithelium_detachment",
        "label_ko": "색소상피박리",
        "region": "macula",
        "min_prob": 0.55,
    },
    {
        "type": "geographic_atrophy",
        "label_ko": "지도형 위축",
        "region": "macula",
        "min_prob": 0.65,
    },
    {
        "type": "choroidal_neovascularization",
        "label_ko": "맥락막신생혈관",
        "region": "macula",
        "min_prob": 0.75,
    },
]


def _macula_center() -> tuple[float, float]:
    return 0.50, 0.50


def generate_amd_lesion_annotations(
    hotspots: list[dict[str, Any]],
    probability: float,
    *,
    eye_side: str = "unknown",
) -> list[dict[str, Any]]:
    p = max(0.0, min(1.0, float(probability)))
    annotations: list[dict[str, Any]] = []
    for spec in AMD_LESION_TYPES:
        if p < float(spec["min_prob"]):
            continue
        conf = min(0.98, p * (0.85 + 0.1 * (p - spec["min_prob"])))
        region = spec["region"]
        if hotspots:
            hs = max(hotspots, key=lambda h: float(h.get("intensity", 0)))
            region = classify_hotspot_region(hs["x"], hs["y"], eye_side)
        annotations.append(
            {
                "type": spec["type"],
                "confidence": round(conf, 3),
                "region": region,
            }
        )
    if not annotations and p >= 0.3:
        cx, cy = _macula_center()
        annotations.append(
            {
                "type": "drusen",
                "confidence": round(p * 0.85, 3),
                "region": classify_hotspot_region(cx, cy, eye_side),
            }
        )
    return annotations


def _resolve_amd_pt_path(onnx_path: Path, meta: dict) -> Path | None:
    models_dir = onnx_path.parent
    names = [
        str(meta.get("pt") or "").strip(),
        str(meta.get("source_checkpoint") or "").strip(),
        "best.pt",
        onnx_path.stem + ".pt",
    ]
    dirs = [models_dir, models_dir / onnx_path.stem, models_dir / "retinal_amd_v1"]
    for d in dirs:
        for name in names:
            if not name:
                continue
            candidate = d / name
            if candidate.is_file():
                return candidate
    return None


def _normalize_amd_state_dict(ckpt: object) -> dict:
    """train_amd.py head.* → torchvision EfficientNet classifier.1.* 매핑."""
    import torch

    if isinstance(ckpt, dict) and "model_state" in ckpt:
        sd = ckpt["model_state"]
    elif isinstance(ckpt, dict) and "state_dict" in ckpt:
        sd = ckpt["state_dict"]
    elif isinstance(ckpt, dict) and ckpt and all(
        isinstance(v, torch.Tensor) for v in ckpt.values()
    ):
        sd = ckpt
    else:
        raise RuntimeError("AMD checkpoint has no loadable state_dict")

    out: dict = {}
    for k, v in sd.items():
        key = k[7:] if k.startswith("module.") else k
        key = key.replace("head.", "classifier.1.")
        out[key] = v
    return out


def _load_amd_weights(model: Any, ckpt: object) -> None:
    sd = _normalize_amd_state_dict(ckpt)
    model.load_state_dict(sd, strict=True)


def _macula_guided_cam(
    proc_h: int,
    proc_w: int,
    probability: float,
) -> np.ndarray:
    cx_n, cy_n = _macula_center()
    cx, cy = int(cx_n * proc_w), int(cy_n * proc_h)
    y_idx, x_idx = np.mgrid[0:proc_h, 0:proc_w]
    sigma = max(proc_w, proc_h) * (0.10 + 0.06 * probability)
    cam = np.exp(
        -((x_idx - cx) ** 2 + (y_idx - cy) ** 2) / (2.0 * sigma**2)
    ).astype(np.float32)
    cam *= 0.5 + 0.5 * probability
    cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-8)
    return cam


def generate_amd_annotated_heatmap(
    image_bytes: bytes,
    probability: float,
    *,
    amd_grade: int = 0,
    eye_side: str = "unknown",
    overlay_alpha: float = 0.45,
) -> dict[str, Any]:
    del amd_grade
    try:
        import cv2
        from PIL import Image

        from services.amd_cnn import _load_meta

        onnx_path = get_amd_model_path()
        meta = _load_meta(onnx_path)
        size = int(meta.get("image_size") or 224)
        pm = resolve_preprocess_mode(str(meta.get("preprocess") or "clahe"))
        eye = _normalize_eye_side(eye_side)

        pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        orig_w, orig_h = pil.size
        proc_np = preprocess_fundus_array(np.array(pil), mode=pm)
        proc_h, proc_w = proc_np.shape[:2]

        cam: np.ndarray | None = None
        gradcam_version = "gradcam++"
        pt_path = _resolve_amd_pt_path(onnx_path, meta)

        if pt_path is not None:
            import torch

            model = _build_glaucoma_classifier()
            try:
                ckpt = torch.load(pt_path, map_location="cpu", weights_only=False)
            except TypeError:
                ckpt = torch.load(pt_path, map_location="cpu")
            _load_amd_weights(model, ckpt)
            device = torch.device("cpu")
            model.to(device).eval()
            target_layer = _resolve_target_layer(model)

            resized = Image.fromarray(proc_np).resize((size, size))
            tensor = torch.from_numpy(np.array(resized)).permute(2, 0, 1).float() / 255.0
            tensor = tensor.unsqueeze(0).to(device)
            tensor.requires_grad_(True)

            gpp = GradCAMPlusPlus(model, target_layer=target_layer)
            cam_small, _ = gpp.generate(tensor, target_class=0)
            cam = cv2.resize(cam_small, (proc_w, proc_h), interpolation=cv2.INTER_CUBIC)
            cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-8)
        else:
            gradcam_version = "probability_guided"
            cam = _macula_guided_cam(proc_h, proc_w, probability)

        heat_u8 = (cam * 255).astype(np.uint8)
        heat_color = cv2.applyColorMap(heat_u8, cv2.COLORMAP_JET)
        heat_rgb = cv2.cvtColor(heat_color, cv2.COLOR_BGR2RGB)
        overlay = (
            (1.0 - overlay_alpha) * proc_np.astype(np.float32)
            + overlay_alpha * heat_rgb.astype(np.float32)
        )
        overlay = np.clip(overlay, 0, 255).astype(np.uint8)

        threshold = float(cam.max()) * 0.80
        hotspots_y, hotspots_x = np.where(cam > threshold)
        hotspot_regions: list[dict[str, Any]] = []
        for x, y in zip(hotspots_x[:10], hotspots_y[:10]):
            hotspot_regions.append(
                {
                    "x": float(x / max(proc_w, 1)),
                    "y": float(y / max(proc_h, 1)),
                    "intensity": float(cam[y, x]),
                    "x_px": int(x),
                    "y_px": int(y),
                }
            )

        lesion_annotations = generate_amd_lesion_annotations(
            hotspot_regions, probability, eye_side=eye
        )
        hotspot_labels = list(
            dict.fromkeys(a["region"] for a in lesion_annotations if a.get("region"))
        )
        if "황반부(macula)" not in hotspot_labels and probability >= 0.3:
            hotspot_labels.insert(0, "macula")

        return {
            "image_base64": _encode_jpeg_b64(overlay, quality=85),
            "resolution": f"{orig_w}x{orig_h}",
            "lesion_annotations": lesion_annotations,
            "hotspot_regions": hotspot_labels,
            "gradcam_version": gradcam_version,
            "heatmap_error": None,
            "heatmap_width": proc_w,
            "heatmap_height": proc_h,
            "cam_resolution": f"{proc_w}x{proc_h}",
            "attention_score": float(cam.max()),
        }
    except Exception as exc:
        log.exception("AMD GradCAM failed")
        return {
            "image_base64": "",
            "resolution": "",
            "lesion_annotations": [],
            "hotspot_regions": [],
            "gradcam_version": None,
            "heatmap_error": str(exc)[:500],
        }


class AMDGradCAMVisualizer:
    async def generate_annotated(
        self,
        image_bytes: bytes,
        probability: float,
        *,
        amd_grade: int = 0,
        eye_side: str = "unknown",
    ) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: generate_amd_annotated_heatmap(
                image_bytes,
                probability,
                amd_grade=amd_grade,
                eye_side=eye_side,
            ),
        )


MYOPIA_LESION_TYPES = [
    {
        "type": "peripapillary_atrophy",
        "label_ko": "시신경 주위 위축",
        "region": "peripapillary",
        "min_prob": 0.35,
    },
    {
        "type": "posterior_staphyloma",
        "label_ko": "후부 포도막",
        "region": "posterior_pole",
        "min_prob": 0.55,
    },
    {
        "type": "lacquer_cracks",
        "label_ko": "옻칠 균열",
        "region": "macula",
        "min_prob": 0.45,
    },
    {
        "type": "choroidal_atrophy",
        "label_ko": "맥락막 위축",
        "region": "mid-periphery",
        "min_prob": 0.50,
    },
    {
        "type": "myopic_maculopathy",
        "label_ko": "근시 황반병증",
        "region": "macula",
        "min_prob": 0.65,
    },
]


def generate_myopia_lesion_annotations(
    hotspots: list[dict[str, Any]],
    probability: float,
    *,
    eye_side: str = "unknown",
) -> list[dict[str, Any]]:
    p = max(0.0, min(1.0, float(probability)))
    annotations: list[dict[str, Any]] = []
    for spec in MYOPIA_LESION_TYPES:
        if p < float(spec["min_prob"]):
            continue
        conf = min(0.98, p * (0.85 + 0.1 * (p - spec["min_prob"])))
        region = spec["region"]
        if hotspots:
            hs = max(hotspots, key=lambda h: float(h.get("intensity", 0)))
            region = classify_hotspot_region(hs["x"], hs["y"], eye_side)
        annotations.append(
            {
                "type": spec["type"],
                "confidence": round(conf, 3),
                "region": region,
            }
        )
    return annotations


def _resolve_myopia_pt_path(onnx_path: Path, meta: dict) -> Path | None:
    models_dir = onnx_path.parent
    names = [
        str(meta.get("pt") or "").strip(),
        str(meta.get("source_checkpoint") or "").strip(),
        "best.pt",
        onnx_path.stem + ".pt",
    ]
    dirs = [models_dir, models_dir / onnx_path.stem, models_dir / "retinal_myopia_v1"]
    for d in dirs:
        for name in names:
            if not name:
                continue
            candidate = d / name
            if candidate.is_file():
                return candidate
    return None


def _normalize_myopia_state_dict(ckpt: object) -> dict:
    """train_myopia.py head.* → torchvision EfficientNet classifier.1.* 매핑."""
    import torch

    if isinstance(ckpt, dict) and "model_state" in ckpt:
        sd = ckpt["model_state"]
    elif isinstance(ckpt, dict) and "state_dict" in ckpt:
        sd = ckpt["state_dict"]
    elif isinstance(ckpt, dict) and ckpt and all(
        isinstance(v, torch.Tensor) for v in ckpt.values()
    ):
        sd = ckpt
    else:
        raise RuntimeError("Myopia checkpoint has no loadable state_dict")

    out: dict = {}
    for k, v in sd.items():
        key = k[7:] if k.startswith("module.") else k
        key = key.replace("head.", "classifier.1.")
        out[key] = v
    return out


def _load_myopia_weights(model: Any, ckpt: object) -> None:
    sd = _normalize_myopia_state_dict(ckpt)
    model.load_state_dict(sd, strict=True)


def generate_myopia_annotated_heatmap(
    image_bytes: bytes,
    probability: float,
    *,
    myopia_grade: int = 0,
    eye_side: str = "unknown",
    overlay_alpha: float = 0.45,
) -> dict[str, Any]:
    del myopia_grade
    try:
        import cv2
        from PIL import Image

        from services.myopia_cnn import _load_meta

        onnx_path = get_myopia_model_path()
        meta = _load_meta(onnx_path)
        size = int(meta.get("image_size") or 224)
        pm = resolve_preprocess_mode(str(meta.get("preprocess") or "clahe"))
        eye = _normalize_eye_side(eye_side)

        pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        orig_w, orig_h = pil.size
        proc_np = preprocess_fundus_array(np.array(pil), mode=pm)
        proc_h, proc_w = proc_np.shape[:2]

        cam: np.ndarray | None = None
        gradcam_version = "gradcam++"
        pt_path = _resolve_myopia_pt_path(onnx_path, meta)

        if pt_path is not None:
            import torch

            model = _build_glaucoma_classifier()
            try:
                ckpt = torch.load(pt_path, map_location="cpu", weights_only=False)
            except TypeError:
                ckpt = torch.load(pt_path, map_location="cpu")
            _load_myopia_weights(model, ckpt)
            device = torch.device("cpu")
            model.to(device).eval()
            target_layer = _resolve_target_layer(model)

            resized = Image.fromarray(proc_np).resize((size, size))
            tensor = torch.from_numpy(np.array(resized)).permute(2, 0, 1).float() / 255.0
            tensor = tensor.unsqueeze(0).to(device)
            tensor.requires_grad_(True)

            gpp = GradCAMPlusPlus(model, target_layer=target_layer)
            cam_small, _ = gpp.generate(tensor, target_class=0)
            cam = cv2.resize(cam_small, (proc_w, proc_h), interpolation=cv2.INTER_CUBIC)
            cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-8)
        else:
            gradcam_version = "probability_guided"
            cam = _macula_guided_cam(proc_h, proc_w, probability)

        heat_u8 = (cam * 255).astype(np.uint8)
        heat_color = cv2.applyColorMap(heat_u8, cv2.COLORMAP_JET)
        heat_rgb = cv2.cvtColor(heat_color, cv2.COLOR_BGR2RGB)
        overlay = (
            (1.0 - overlay_alpha) * proc_np.astype(np.float32)
            + overlay_alpha * heat_rgb.astype(np.float32)
        )
        overlay = np.clip(overlay, 0, 255).astype(np.uint8)

        threshold = float(cam.max()) * 0.80
        hotspots_y, hotspots_x = np.where(cam > threshold)
        hotspot_regions: list[dict[str, Any]] = []
        for x, y in zip(hotspots_x[:10], hotspots_y[:10]):
            hotspot_regions.append(
                {
                    "x": float(x / max(proc_w, 1)),
                    "y": float(y / max(proc_h, 1)),
                    "intensity": float(cam[y, x]),
                    "x_px": int(x),
                    "y_px": int(y),
                }
            )

        lesion_annotations = generate_myopia_lesion_annotations(
            hotspot_regions, probability, eye_side=eye
        )
        hotspot_labels = list(
            dict.fromkeys(a["region"] for a in lesion_annotations if a.get("region"))
        )

        return {
            "image_base64": _encode_jpeg_b64(overlay, quality=85),
            "resolution": f"{orig_w}x{orig_h}",
            "lesion_annotations": lesion_annotations,
            "hotspot_regions": hotspot_labels,
            "gradcam_version": gradcam_version,
            "heatmap_error": None,
            "heatmap_width": proc_w,
            "heatmap_height": proc_h,
            "cam_resolution": f"{proc_w}x{proc_h}",
            "attention_score": float(cam.max()),
        }
    except Exception as exc:
        log.exception("Myopia GradCAM failed")
        return {
            "image_base64": "",
            "resolution": "",
            "lesion_annotations": [],
            "hotspot_regions": [],
            "gradcam_version": None,
            "heatmap_error": str(exc)[:500],
        }


class MyopiaGradCAMVisualizer:
    async def generate_annotated(
        self,
        image_bytes: bytes,
        probability: float,
        *,
        myopia_grade: int = 0,
        eye_side: str = "unknown",
    ) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: generate_myopia_annotated_heatmap(
                image_bytes,
                probability,
                myopia_grade=myopia_grade,
                eye_side=eye_side,
            ),
        )


class GlaucomaGradCAMVisualizer:
    """retinal_glaucoma_v2 — GradCAM++ / probability-guided."""

    async def generate_annotated(
        self,
        image_bytes: bytes,
        probability: float,
        *,
        glaucoma_grade: int = 0,
        eye_side: str = "unknown",
    ) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: generate_glaucoma_annotated_heatmap(
                image_bytes,
                probability,
                glaucoma_grade=glaucoma_grade,
                eye_side=eye_side,
            ),
        )


class GradCAMService:
    """DR / Glaucoma / AMD / Myopia 모델 타입 자동 분기."""

    def __init__(self) -> None:
        self._dr = GradCAMVisualizer()
        self._glaucoma = GlaucomaGradCAMVisualizer()
        self._amd = AMDGradCAMVisualizer()
        self._myopia = MyopiaGradCAMVisualizer()

    @staticmethod
    def detect_model_type(model_path: str | Path | None) -> str:
        p = str(model_path or "").lower()
        if "myopia" in p:
            return "myopia"
        if "amd" in p:
            return "amd"
        if "glaucoma" in p:
            return "glaucoma"
        return "dr"

    async def generate_dr_heatmap(
        self,
        image_bytes: bytes,
        dr_grade: int,
        *,
        eye_side: str = "unknown",
        lang: str = "ko",
    ) -> dict[str, Any]:
        return await self._dr.generate_annotated(
            image_bytes, dr_grade, eye_side=eye_side, lang=lang
        )

    async def generate_glaucoma_heatmap(
        self,
        image: bytes,
        model_path: str,
        probability: float,
        *,
        glaucoma_grade: int = 0,
        eye_side: str = "unknown",
    ) -> dict[str, Any]:
        del model_path
        return await self._glaucoma.generate_annotated(
            image,
            probability,
            glaucoma_grade=glaucoma_grade,
            eye_side=eye_side,
        )

    async def generate_amd_heatmap(
        self,
        image: bytes,
        model_path: str,
        probability: float,
        *,
        amd_grade: int = 0,
        eye_side: str = "unknown",
    ) -> dict[str, Any]:
        del model_path
        return await self._amd.generate_annotated(
            image,
            probability,
            amd_grade=amd_grade,
            eye_side=eye_side,
        )

    async def generate_myopia_heatmap(
        self,
        image: bytes,
        model_path: str,
        probability: float,
        *,
        myopia_grade: int = 0,
        eye_side: str = "unknown",
    ) -> dict[str, Any]:
        del model_path
        return await self._myopia.generate_annotated(
            image,
            probability,
            myopia_grade=myopia_grade,
            eye_side=eye_side,
        )
