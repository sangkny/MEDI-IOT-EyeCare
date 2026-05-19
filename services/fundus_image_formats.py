"""안저 이미지 포맷 검증·정규화 (업로드·Lab 공통)."""
from __future__ import annotations

import io
from pathlib import Path

# 확장자 → MIME (업로드·Lab UI accept 와 동기화)
EXTENSION_TO_MIME: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heif",
}

ALLOWED_EXTENSIONS: frozenset[str] = frozenset(EXTENSION_TO_MIME)

ALLOWED_MIME_TYPES: frozenset[str] = frozenset(EXTENSION_TO_MIME.values()) | {
    "image/jpg",
    "application/octet-stream",
}

MAX_FUNDUS_BYTES = 20 * 1024 * 1024


def extension_from_filename(filename: str | None) -> str:
    if not filename:
        return ".jpg"
    ext = Path(filename).suffix.lower()
    return ext if ext in ALLOWED_EXTENSIONS else ""


def resolve_mime(content_type: str | None, filename: str | None) -> str:
    ext = extension_from_filename(filename)
    if ext:
        return EXTENSION_TO_MIME[ext]
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct in ALLOWED_MIME_TYPES and ct.startswith("image/"):
        return "image/jpeg" if ct == "image/jpg" else ct
    return "image/jpeg"


def validate_fundus_upload(
    content: bytes,
    *,
    filename: str | None = None,
    content_type: str | None = None,
    max_bytes: int = MAX_FUNDUS_BYTES,
) -> tuple[str, str]:
    """바이트·파일명 검증 → (mime_type, detected_format)."""
    if not content:
        raise ValueError("empty image file")
    if len(content) > max_bytes:
        raise ValueError(f"file too large (max {max_bytes // (1024*1024)}MB)")

    ext = extension_from_filename(filename)
    if filename and not ext:
        raise ValueError(
            f"unsupported extension; allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    detected = _detect_format(content)
    if detected == "unknown" and not ext:
        raise ValueError("not a recognized image format")

    fmt = detected if detected != "unknown" else ext.lstrip(".")
    mime = resolve_mime(content_type, filename)
    return mime, fmt


def _detect_format(content: bytes) -> str:
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if content[:2] == b"\xff\xd8":
        return "jpeg"
    if content[:4] in (b"II*\x00", b"MM\x00*"):
        return "tiff"
    if content[:2] == b"BM":
        return "bmp"
    if content[:4] == b"RIFF" and len(content) > 12 and content[8:12] == b"WEBP":
        return "webp"
    try:
        from PIL import Image

        with Image.open(io.BytesIO(content)) as im:
            return (im.format or "unknown").lower()
    except Exception:
        return "unknown"


def normalize_for_cnn(content: bytes) -> bytes:
    """CNN 입력용 RGB 바이트 (PIL 있으면 변환, 없으면 원본)."""
    try:
        from PIL import Image

        with Image.open(io.BytesIO(content)) as im:
            rgb = im.convert("RGB")
            buf = io.BytesIO()
            rgb.save(buf, format="JPEG", quality=92)
            return buf.getvalue()
    except Exception:
        return content


__all__ = [
    "ALLOWED_EXTENSIONS",
    "ALLOWED_MIME_TYPES",
    "MAX_FUNDUS_BYTES",
    "validate_fundus_upload",
    "normalize_for_cnn",
    "resolve_mime",
]
