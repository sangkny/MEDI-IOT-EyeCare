"""DICOM foundation — detect/parse/extract without PACS networking.

PARTIAL: requires optional pydicom. Never commit PHI DICOM files.
"""
from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("services.dicom_foundation")

DICOM_ADAPTER_VERSION = "dicom-foundation-v1-partial"


def is_dicom_bytes(data: bytes) -> bool:
    if len(data) < 132:
        return False
    return data[128:132] == b"DICM"


def parse_dicom_safe(data: bytes) -> dict[str, Any]:
    """Parse metadata with PHI redaction guard. Pixel extract when possible."""
    if not is_dicom_bytes(data):
        return {"is_dicom": False, "adapter_version": DICOM_ADAPTER_VERSION}

    try:
        import pydicom
        from pydicom.pixel_data_handlers.util import convert_color_space
    except ImportError:
        return {
            "is_dicom": True,
            "adapter_version": DICOM_ADAPTER_VERSION,
            "status": "PARTIAL",
            "error": "pydicom_not_installed",
            "note": "Install pydicom in runtime to enable pixel extraction",
        }

    try:
        from io import BytesIO

        ds = pydicom.dcmread(BytesIO(data), force=True)
    except Exception as exc:  # noqa: BLE001
        return {
            "is_dicom": True,
            "adapter_version": DICOM_ADAPTER_VERSION,
            "status": "FAILED",
            "error": type(exc).__name__,
        }

    # De-identification guard: never return PatientName / PatientID / AccessionNumber values
    phi_tags_present = []
    for tag_name in ("PatientName", "PatientID", "PatientBirthDate", "AccessionNumber"):
        if hasattr(ds, tag_name) and getattr(ds, tag_name):
            phi_tags_present.append(tag_name)

    meta = {
        "is_dicom": True,
        "adapter_version": DICOM_ADAPTER_VERSION,
        "status": "OK",
        "modality": str(getattr(ds, "Modality", "") or ""),
        "rows": int(getattr(ds, "Rows", 0) or 0),
        "columns": int(getattr(ds, "Columns", 0) or 0),
        "photometric": str(getattr(ds, "PhotometricInterpretation", "") or ""),
        "phi_tags_present": phi_tags_present,
        "phi_redacted": True,
        "note": "Patient-identifying DICOM tags are never returned as values",
    }

    pixels = None
    try:
        arr = ds.pixel_array
        if hasattr(arr, "shape"):
            meta["pixel_shape"] = list(arr.shape)
            meta["pixel_extractable"] = True
            # Do not return raw pixels here — caller may convert separately
            pixels = arr
    except Exception as exc:  # noqa: BLE001
        meta["pixel_extractable"] = False
        meta["pixel_error"] = type(exc).__name__

    return {"meta": meta, "has_pixels": pixels is not None}


def dicom_to_png_bytes(data: bytes) -> tuple[bytes | None, dict[str, Any]]:
    """Convert DICOM pixels to PNG bytes for serving path. Returns (png|None, info)."""
    info = parse_dicom_safe(data)
    if not info.get("is_dicom"):
        return None, info
    if info.get("status") == "PARTIAL":
        return None, info
    try:
        import numpy as np
        import pydicom
        from io import BytesIO
        from PIL import Image

        ds = pydicom.dcmread(BytesIO(data), force=True)
        arr = ds.pixel_array
        if arr.ndim == 3 and arr.shape[-1] == 3:
            rgb = arr
        else:
            # normalize to 8-bit gray then RGB
            a = arr.astype("float64")
            a = a - a.min()
            if a.max() > 0:
                a = a / a.max() * 255.0
            g = a.astype("uint8")
            rgb = np.stack([g, g, g], axis=-1)
        buf = BytesIO()
        Image.fromarray(rgb).save(buf, format="PNG")
        return buf.getvalue(), {**info, "converted": True}
    except Exception as exc:  # noqa: BLE001
        return None, {**info, "converted": False, "convert_error": type(exc).__name__}
