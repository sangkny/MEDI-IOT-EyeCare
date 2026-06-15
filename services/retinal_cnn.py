"""Retinal DR CNN — EfficientNet / MSEF-Net 5-class (D R4-ML).

문헌·벤치마크 (2023–2025):
  - **MSEF-Net** (multi-scale EfficientNet fusion): Messidor-1 ~97.5% acc.
  - **MAFNet**: Messidor-2 QWK ~0.917.
  - **RETFound** (Nature 2023, MAE): 자기지도 fundus — ``retinal_foundation.py``.

전처리: CLAHE · Ben Graham (APTOS/Kaggle DR 대회 관행).
운영 기본 백본: ``efficientnet_b4`` · 멀티스케일: ``msef_net``.

환경:
  ``MEDI_CNN_ARCH`` — efficientnet_b0 | efficientnet_b4 | efficientnet_b4_se | efficientnet_v2_s | msef_net
  ``MEDI_CNN_PREPROCESS`` — none | clahe | ben_graham | both | enhanced | v2
"""
from __future__ import annotations

import io
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np

# import_messidor2 와 동일 매핑
DR_TO_ICD10: dict[int, str | None] = {
    0: None,
    1: "H35.0",
    2: "H36.0",
    3: "H36.0",
    4: "H36.0",
}

DR_TO_SEVERITY: dict[int, str] = {
    0: "normal",
    1: "mild",
    2: "moderate",
    3: "severe",
    4: "severe",
}

DR_GRADE_CONDITION: dict[int, tuple[str, str]] = {
    0: ("normal_fundus", "정상 안저"),
    1: ("mild_diabetic_retinopathy", "경증 당뇨망막병증"),
    2: ("moderate_diabetic_retinopathy", "중등도 당뇨망막병증"),
    3: ("severe_diabetic_retinopathy", "중증 당뇨망막병증"),
    4: ("proliferative_diabetic_retinopathy", "증식성 당뇨망막병증"),
}

DR_NUM_CLASSES = 5
DEFAULT_IMAGE_SIZE = 224
DEFAULT_CNN_ARCH = "efficientnet_b4"
DEFAULT_PREPROCESS = "clahe"

PreprocessMode = Literal["none", "clahe", "ben_graham", "both", "enhanced", "v2"]

ARCH_ALIASES: dict[str, str] = {
    "efficientnet-b0": "efficientnet_b0",
    "efficientnet-b4": "efficientnet_b4",
    "efficientnet-v2-s": "efficientnet_v2_s",
    "msef-net": "msef_net",
    "msef_net": "msef_net",
    "b0": "efficientnet_b0",
    "b4": "efficientnet_b4",
    "b4_se": "efficientnet_b4_se",
    "efficientnet-b4-se": "efficientnet_b4_se",
    "v2s": "efficientnet_v2_s",
}

SUPPORTED_CNN_ARCHS: frozenset[str] = frozenset(
    {
        "efficientnet_b0",
        "efficientnet_b4",
        "efficientnet_b4_se",
        "efficientnet_v2_s",
        "msef_net",
    }
)

MSEF_SMALL_DIM = 1280
MSEF_LARGE_DIM = 1792


@dataclass(frozen=True)
class DrPrediction:
    dr_grade: int
    confidence: float
    icd10_code: str
    severity: str
    probabilities: tuple[float, ...]


def resolve_cnn_arch(name: str | None = None) -> str:
    raw = (name or os.getenv("MEDI_CNN_ARCH") or DEFAULT_CNN_ARCH).strip().lower()
    return ARCH_ALIASES.get(raw, raw)


def resolve_preprocess_mode(mode: str | None = None) -> PreprocessMode:
    raw = (mode or os.getenv("MEDI_CNN_PREPROCESS") or DEFAULT_PREPROCESS).strip().lower()
    if raw in ("none", "clahe", "ben_graham", "both", "enhanced", "v2"):
        return raw  # type: ignore[return-value]
    return "clahe"


def apply_clahe(image: np.ndarray) -> np.ndarray:
    """LAB L-channel CLAHE (fundus 대비 강화)."""
    import cv2

    if image.dtype != np.uint8:
        image = np.clip(image, 0, 255).astype(np.uint8)
    lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    lab[:, :, 0] = clahe.apply(lab[:, :, 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)


def ben_graham_preprocess(image: np.ndarray, sigma_x: float = 10.0) -> np.ndarray:
    """Ben Graham 정규화 (Kaggle DR 대회 전처리)."""
    import cv2

    if image.dtype != np.uint8:
        image = np.clip(image, 0, 255).astype(np.uint8)
    blurred = cv2.GaussianBlur(image, (0, 0), sigma_x)
    return cv2.addWeighted(image, 4, blurred, -4, 128)


def preprocess_fundus_array(
    image: np.ndarray,
    *,
    mode: PreprocessMode | str | None = None,
) -> np.ndarray:
    """RGB uint8 HxWx3 → 전처리된 RGB."""
    pm = resolve_preprocess_mode(str(mode) if mode else None)
    out = image
    if pm in ("v2", "enhanced"):
        import cv2

        from services.fundus_enhancement import enhance_fundus

        bgr = cv2.cvtColor(out, cv2.COLOR_RGB2BGR)
        bgr = enhance_fundus(
            bgr,
            size=DEFAULT_IMAGE_SIZE,
            use_dcp=(pm == "enhanced"),
        )
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    if pm in ("clahe", "both"):
        out = apply_clahe(out)
    if pm in ("ben_graham", "both"):
        out = ben_graham_preprocess(out)
    return out


def preprocess_fundus_bytes(
    image_bytes: bytes,
    *,
    mode: PreprocessMode | str = "v2",
) -> bytes:
    """v2/enhanced 실시간 전처리 — API comprehensive용 JPEG bytes."""
    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    arr = preprocess_fundus_array(np.array(img), mode=mode)
    out = Image.fromarray(arr)
    buf = io.BytesIO()
    out.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def enhance_fundus_bytes(image_bytes: bytes) -> bytes:
    """v2 + local DCP — API preprocess=enhanced."""
    return preprocess_fundus_bytes(image_bytes, mode="enhanced")


def dr_prediction_from_logits(logits: Any) -> DrPrediction:
    """``logits`` shape ``(5,)`` 또는 ``(1,5)`` — torch tensor 또는 list."""
    try:
        import torch

        if hasattr(logits, "detach"):
            t = logits.detach().float().cpu()
            if t.ndim == 2:
                t = t[0]
            probs = torch.softmax(t, dim=0).tolist()
        else:
            raise TypeError("not a tensor")
    except Exception:
        raw = list(logits[0] if isinstance(logits[0], (list, tuple)) else logits)
        if len(raw) != DR_NUM_CLASSES:
            raise ValueError(f"expected {DR_NUM_CLASSES} logits, got {len(raw)}")
        m = max(raw)
        ex = [x - m for x in raw]
        import math

        exp = [math.exp(x) for x in ex]
        s = sum(exp)
        probs = [e / s for e in exp]

    grade = int(max(range(DR_NUM_CLASSES), key=lambda i: probs[i]))
    conf = float(probs[grade])
    icd = DR_TO_ICD10.get(grade) or "H57.9"
    sev = DR_TO_SEVERITY.get(grade, "mild")
    return DrPrediction(
        dr_grade=grade,
        confidence=conf,
        icd10_code=icd,
        severity=sev,
        probabilities=tuple(float(p) for p in probs),
    )


def dr_prediction_to_parsed(pred: DrPrediction) -> dict[str, Any]:
    """``EyeAnalyzer`` / OntologyValidator 와 동일 dict 스키마."""
    cond, cond_kr = DR_GRADE_CONDITION.get(
        pred.dr_grade, ("diabetic_retinopathy", "당뇨망막병증")
    )
    return {
        "condition": cond,
        "condition_kr": cond_kr,
        "icd10_code": pred.icd10_code,
        "severity": pred.severity,
        "confidence": pred.confidence,
        "dr_grade": pred.dr_grade,
        "probabilities": list(pred.probabilities),
    }


def preprocess_fundus_bytes(
    image_bytes: bytes,
    *,
    image_size: int = DEFAULT_IMAGE_SIZE,
    preprocess_mode: PreprocessMode | str | None = None,
) -> Any:
    """RGB fundus → ``(1,3,H,W)`` float32 tensor (torch)."""
    import torch
    from PIL import Image
    from torchvision import transforms as T

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    arr = np.array(img)
    arr = preprocess_fundus_array(arr, mode=preprocess_mode)
    img = Image.fromarray(arr)
    img = img.resize((image_size, image_size))
    t = T.ToTensor()(img).unsqueeze(0)
    return t.to(dtype=torch.float32)


def _efficientnet_embed(model: Any, x: Any) -> Any:
    import torch

    x = model.features(x)
    x = model.avgpool(x)
    return torch.flatten(x, 1)


def _load_efficientnet_backbone(arch_key: str, *, pretrained: bool):
    import torch
    from torchvision import models

    factories = {
        "efficientnet_b0": models.efficientnet_b0,
        "efficientnet_b4": models.efficientnet_b4,
        "efficientnet_v2_s": models.efficientnet_v2_s,
    }
    weights = None
    if pretrained:
        weight_enums = {
            "efficientnet_b0": ("EfficientNet_B0_Weights", "IMAGENET1K_V1"),
            "efficientnet_b4": ("EfficientNet_B4_Weights", "IMAGENET1K_V1"),
            "efficientnet_v2_s": ("EfficientNet_V2_S_Weights", "IMAGENET1K_V1"),
        }
        mod_name, attr = weight_enums[arch_key]
        try:
            import torchvision.models as tvm

            weights = getattr(getattr(tvm, mod_name), attr)
        except Exception:
            weights = "IMAGENET1K_V1"
    return factories[arch_key](weights=weights)


def build_efficientnet_b4_se(
    *,
    num_classes: int = DR_NUM_CLASSES,
    pretrained: bool = False,
):
    """EfficientNet-B4 + SE Block (마지막 feature map 채널 어텐션)."""
    import torch
    import torch.nn as nn

    class SEBlock(nn.Module):
        def __init__(self, channels: int, reduction: int = 16) -> None:
            super().__init__()
            hidden = max(channels // reduction, 8)
            self.squeeze = nn.AdaptiveAvgPool2d(1)
            self.excitation = nn.Sequential(
                nn.Linear(channels, hidden, bias=False),
                nn.ReLU(inplace=True),
                nn.Linear(hidden, channels, bias=False),
                nn.Sigmoid(),
            )

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            b, c, _, _ = x.size()
            y = self.squeeze(x).view(b, c)
            y = self.excitation(y).view(b, c, 1, 1)
            return x * y.expand_as(x)

    class EfficientNetB4WithSE(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            backbone = _load_efficientnet_backbone("efficientnet_b4", pretrained=pretrained)
            self.features = backbone.features
            self.avgpool = backbone.avgpool
            feat_dim = backbone.classifier[1].in_features
            self.se = SEBlock(feat_dim)
            self.dropout = nn.Dropout(p=0.3)
            self.classifier = nn.Linear(feat_dim, num_classes)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            x = self.features(x)
            x = self.se(x)
            x = self.avgpool(x)
            x = torch.flatten(x, 1)
            x = self.dropout(x)
            return self.classifier(x)

    return EfficientNetB4WithSE(), "efficientnet_b4_se"


def build_msef_net(*, num_classes: int = DR_NUM_CLASSES, pretrained: bool = False):
    """Multi-Scale EfficientNet Fusion (MSEF-Net 스타일)."""
    import torch
    import torch.nn as nn

    class MSEFNet(nn.Module):
        """Multi-Scale EfficientNet Fusion — B0(소) + B4(대) 피처 융합."""

        def __init__(self) -> None:
            super().__init__()
            self.backbone_small = _load_efficientnet_backbone("efficientnet_b0", pretrained=pretrained)
            self.backbone_large = _load_efficientnet_backbone("efficientnet_b4", pretrained=pretrained)
            self.fusion = nn.Linear(MSEF_SMALL_DIM + MSEF_LARGE_DIM, 512)
            self.dropout = nn.Dropout(p=0.2)
            self.classifier = nn.Linear(512, num_classes)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            fs = _efficientnet_embed(self.backbone_small, x)
            fl = _efficientnet_embed(self.backbone_large, x)
            h = torch.relu(self.fusion(torch.cat([fs, fl], dim=1)))
            h = self.dropout(h)
            return self.classifier(h)

    return MSEFNet(), "msef_net"


def build_dr_classifier(
    *,
    arch: str | None = None,
    num_classes: int = DR_NUM_CLASSES,
    pretrained: bool = False,
):
    """EfficientNet 또는 MSEF-Net 분류기."""
    import torch

    arch_key = resolve_cnn_arch(arch)
    if arch_key == "msef_net":
        return build_msef_net(num_classes=num_classes, pretrained=pretrained)
    if arch_key == "efficientnet_b4_se":
        return build_efficientnet_b4_se(num_classes=num_classes, pretrained=pretrained)

    if arch_key not in SUPPORTED_CNN_ARCHS:
        raise ValueError(
            f"unsupported MEDI_CNN_ARCH={arch_key!r}; "
            f"choose from {sorted(SUPPORTED_CNN_ARCHS)}"
        )

    model = _load_efficientnet_backbone(arch_key, pretrained=pretrained)
    in_features = model.classifier[1].in_features
    model.classifier[1] = torch.nn.Linear(in_features, num_classes)
    return model, arch_key


# ── 호환 API (HANDOVER / 스크립트) ─────────────────────────────
def build_model(arch: str, num_classes: int = DR_NUM_CLASSES):
    """레거시/스모크 스크립트 호환용 alias.

    반환: (model, resolved_arch)
    """
    return build_dr_classifier(arch=arch, num_classes=num_classes, pretrained=False)


def load_manifest_entries(manifest_path: Path, split: str = "train") -> list[dict]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if split == "test" and "test" not in data and "val" in data:
        split = "val"
    entries = data.get(split) or []
    if not isinstance(entries, list):
        raise ValueError(f"manifest split {split!r} invalid")
    return entries


def load_image_tensor_from_path(
    path: Path,
    *,
    image_size: int = DEFAULT_IMAGE_SIZE,
    preprocess_mode: PreprocessMode | str | None = None,
) -> Any:
    """파일 경로 → (1,3,H,W) tensor."""
    from PIL import Image
    from torchvision import transforms as T

    import torch

    img = Image.open(path).convert("RGB")
    arr = preprocess_fundus_array(np.array(img), mode=preprocess_mode)
    img = Image.fromarray(arr).resize((image_size, image_size))
    return T.ToTensor()(img).unsqueeze(0).to(dtype=torch.float32)


def resolve_gradcam_pt_path(cnn_model_path: Path, meta: dict | None = None) -> Path:
    """ONNX 추론 경로에 대응하는 GradCAM용 .pt 체크포인트."""
    from services.gradcam import _resolve_pt_path

    if meta is None:
        meta_path = cnn_model_path.with_name(cnn_model_path.stem + ".meta.json")
        if meta_path.is_file():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        else:
            meta = {}
    return _resolve_pt_path(cnn_model_path, meta)


__all__ = [
    "DR_NUM_CLASSES",
    "DEFAULT_IMAGE_SIZE",
    "DEFAULT_CNN_ARCH",
    "DEFAULT_PREPROCESS",
    "SUPPORTED_CNN_ARCHS",
    "DrPrediction",
    "apply_clahe",
    "ben_graham_preprocess",
    "preprocess_fundus_array",
    "dr_prediction_from_logits",
    "dr_prediction_to_parsed",
    "preprocess_fundus_bytes",
    "build_dr_classifier",
    "build_model",
    "build_efficientnet_b4_se",
    "build_msef_net",
    "resolve_cnn_arch",
    "resolve_preprocess_mode",
    "load_manifest_entries",
    "load_image_tensor_from_path",
    "resolve_gradcam_pt_path",
    "DR_TO_ICD10",
    "DR_TO_SEVERITY",
    "DR_GRADE_CONDITION",
]
