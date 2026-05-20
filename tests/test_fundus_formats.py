"""Fundus 이미지 포맷 검증 (Mock 0)."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

from services.fundus_image_formats import validate_fundus_upload


def test_validate_png_magic() -> None:
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    mime, fmt = validate_fundus_upload(png, filename="x.png")
    assert mime == "image/png"
    assert fmt == "png"


def test_reject_unknown_extension() -> None:
    with pytest.raises(ValueError, match="unsupported extension"):
        validate_fundus_upload(b"data", filename="file.xyz")
