"""
파일명: test_fundus_formats.py
목적: fundus formats.py 단위·통합 테스트
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가


Fundus 이미지 포맷 검증 (Mock 0).
"""
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
