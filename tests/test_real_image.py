"""Phase 2 W7 — PIL 전처리·VISION 온톨로지 훅."""
from __future__ import annotations

import io
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.image_processor import ImageProcessor


def test_preprocess_respects_max_edge(tmp_path: Path) -> None:
    from PIL import Image

    path = tmp_path / "wide.png"
    Image.new("RGB", (2048, 640), color=(10, 20, 80)).save(path)
    ip = ImageProcessor(max_edge=1024)
    raw, fmt = ip.preprocess(path)
    assert fmt == "jpeg"
    im2 = Image.open(io.BytesIO(raw))
    assert max(im2.size) <= 1024


@pytest.mark.asyncio
async def test_analyze_with_vision_passthrough(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from PIL import Image
    import services.eye_analyzer as eye_mod

    path = tmp_path / "f.jpg"
    Image.new("RGB", (640, 480), color=(200, 5, 5)).save(path, format="JPEG")

    fake_ar = MagicMock()
    fake_ar.ontology_passed = False
    fake_ar.ontology_errors = ["시뮬레이션"]
    monkeypatch.setattr(
        eye_mod.EyeAnalyzer,
        "analyze_image_file",
        AsyncMock(return_value=fake_ar),
        raising=True,
    )

    out = await ImageProcessor().analyze_with_vision(path, exam_type="fundus")
    assert out.ontology_passed is False
    assert "시뮬레이션" in out.ontology_errors[0]


@pytest.mark.asyncio
async def test_medical_placeholder_icd() -> None:
    proc = ImageProcessor()
    vr = await proc.validate_medical_placeholder(
        diagnosis_code="H36.0",
        examination_date=str(date.today()),
        eye_condition="diabetic_retinopathy",
    )
    assert isinstance(vr.passed, bool)
