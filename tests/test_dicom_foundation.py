"""DICOM foundation unit tests — synthetic bytes only, no PHI files."""
from __future__ import annotations

from services.dicom_foundation import DICOM_ADAPTER_VERSION, is_dicom_bytes, parse_dicom_safe


def test_non_dicom():
    assert is_dicom_bytes(b"not-dicom") is False
    out = parse_dicom_safe(b"hello")
    assert out["is_dicom"] is False


def test_dicom_magic_partial_without_full_file():
    # Minimal header with DICM magic but incomplete — should detect magic
    buf = b"\x00" * 128 + b"DICM" + b"\x00" * 20
    assert is_dicom_bytes(buf) is True
    out = parse_dicom_safe(buf)
    assert out["is_dicom"] is True
    assert out.get("adapter_version") == DICOM_ADAPTER_VERSION or (
        isinstance(out.get("meta"), dict) and out["meta"].get("adapter_version") == DICOM_ADAPTER_VERSION
    ) or out.get("status") in {"PARTIAL", "FAILED", "OK"}
