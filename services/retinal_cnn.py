"""Retinal DR CNN — EfficientNet 계열 5-class (D R4-ML).

문헌·벤치마크 (2024–2025, Messidor / APTOS / EyePACS):
  - **MSEF-Net** (multi-scale EfficientNet fusion): Messidor-1 ~97.5% acc.
  - **MAFNet**: Messidor-2 QWK ~0.917.
  - 단일 백본: EfficientNet-B4/B0 + attention 이 DR 분류에서 ResNet/DenseNet 대비 우수한 경우가 많음.

운영 기본값: ``efficientnet_b4`` (B0 대비 표현력↑, torchvision 네이티브).
학습: ``scripts/train_retinal.py`` · 추론: ``CnnRetinalBackend`` (D3).

환경: ``MEDI_CNN_ARCH`` = ``efficientnet_b0`` | ``efficientnet_b4`` | ``efficientnet_v2_s``
"""
from __future__ import annotations

import io
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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

ARCH_ALIASES: dict[str, str] = {
    "efficientnet-b0": "efficientnet_b0",
    "efficientnet-b4": "efficientnet_b4",
    "efficientnet-v2-s": "efficientnet_v2_s",
    "b0": "efficientnet_b0",
    "b4": "efficientnet_b4",
    "v2s": "efficientnet_v2_s",
}

SUPPORTED_CNN_ARCHS: frozenset[str] = frozenset(
    {"efficientnet_b0", "efficientnet_b4", "efficientnet_v2_s"}
)


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
) -> Any:
    """RGB fundus → ``(1,3,H,W)`` float32 tensor (torch)."""
    import torch
    from PIL import Image
    from torchvision import transforms as T

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img = img.resize((image_size, image_size))
    t = T.ToTensor()(img).unsqueeze(0)
    return t.to(dtype=torch.float32)


def build_dr_classifier(
    *,
    arch: str | None = None,
    num_classes: int = DR_NUM_CLASSES,
    pretrained: bool = False,
):
    """EfficientNet 분류 헤드 (torchvision)."""
    import torch
    from torchvision import models

    arch_key = resolve_cnn_arch(arch)
    if arch_key not in SUPPORTED_CNN_ARCHS:
        raise ValueError(
            f"unsupported MEDI_CNN_ARCH={arch_key!r}; "
            f"choose from {sorted(SUPPORTED_CNN_ARCHS)}"
        )

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

    factories = {
        "efficientnet_b0": models.efficientnet_b0,
        "efficientnet_b4": models.efficientnet_b4,
        "efficientnet_v2_s": models.efficientnet_v2_s,
    }
    model = factories[arch_key](weights=weights)
    if arch_key.startswith("efficientnet_v2"):
        in_features = model.classifier[1].in_features
        model.classifier[1] = torch.nn.Linear(in_features, num_classes)
    else:
        in_features = model.classifier[1].in_features
        model.classifier[1] = torch.nn.Linear(in_features, num_classes)
    return model, arch_key


def load_manifest_entries(manifest_path: Path, split: str = "train") -> list[dict]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = data.get(split) or []
    if not isinstance(entries, list):
        raise ValueError(f"manifest split {split!r} invalid")
    return entries


__all__ = [
    "DR_NUM_CLASSES",
    "DEFAULT_IMAGE_SIZE",
    "DEFAULT_CNN_ARCH",
    "SUPPORTED_CNN_ARCHS",
    "DrPrediction",
    "dr_prediction_from_logits",
    "dr_prediction_to_parsed",
    "preprocess_fundus_bytes",
    "build_dr_classifier",
    "resolve_cnn_arch",
    "load_manifest_entries",
    "DR_TO_ICD10",
    "DR_TO_SEVERITY",
    "DR_GRADE_CONDITION",
]
