"""Serving preprocessing lock regression — training aug must not appear."""
from __future__ import annotations

import io

import numpy as np
from PIL import Image

from services.preprocessing_lock import (
    PREPROCESSING_VERSION,
    SERVING_LOCKED_DEFAULT_MODE,
    TRAINING_AUGMENTATION_FORBIDDEN_IN_SERVING,
)
from services.retinal_cnn import preprocess_fundus_array, resolve_preprocess_mode


def test_preprocessing_version_constant():
    assert PREPROCESSING_VERSION == "retinal-preproc-v1"
    assert SERVING_LOCKED_DEFAULT_MODE == "none"
    assert TRAINING_AUGMENTATION_FORBIDDEN_IN_SERVING is True


def test_serving_none_is_identity_shape():
    rng = np.random.default_rng(42)
    arr = (rng.random((64, 64, 3)) * 255).astype(np.uint8)
    out = preprocess_fundus_array(arr, mode="none")
    assert out.shape == arr.shape
    assert out.dtype == arr.dtype
    # mode none must not alter pixels
    assert np.array_equal(out, arr)


def test_resolve_none():
    assert resolve_preprocess_mode("none") == "none"
