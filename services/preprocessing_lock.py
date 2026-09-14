"""Serving preprocessing lock for MVP-02 — does not change model math."""
from __future__ import annotations

PREPROCESSING_VERSION = "retinal-preproc-v1"

# Documented serving contract for mode=none (v10c meta default):
# - decode RGB
# - resize to model input size (EfficientNet-B4 path, typically 380/512 per caller)
# - float32 / ImageNet-style normalization inside v10_cnn / onnx session prep
# - NO RandomHorizontalFlip / ColorJitter (training-only)
#
# Other modes (clahe, ben_graham, both, v2, enhanced) remain available via
# services.retinal_cnn.resolve_preprocess_mode but MVP clinical path defaults to none.

SERVING_LOCKED_DEFAULT_MODE = "none"
TRAINING_AUGMENTATION_FORBIDDEN_IN_SERVING = True
