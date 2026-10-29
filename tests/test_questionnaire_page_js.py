"""설문 HTML 스크립트가 구문 오류 없이 핸들러를 등록하는지 확인한다."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_HARNESS = Path(__file__).resolve().parent / "questionnaire_page_harness.mjs"
_PAGE = Path(__file__).resolve().parents[1] / "static" / "questionnaire" / "index.html"

pytestmark = pytest.mark.unit


def test_questionnaire_page_rejects_malformed_object_spread() -> None:
    text = _PAGE.read_text(encoding="utf-8")
    assert "Object ...(" not in text
    assert "{ ...(options.headers || {}), Authorization:" in text


def test_questionnaire_page_registers_handlers_and_clears_on_denial() -> None:
    node = shutil.which("node")
    assert node, "node is required to execute the questionnaire script"
    result = subprocess.run(
        [node, str(_HARNESS)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for label in (
        "questionnaire script parses",
        "questionnaire handlers registered",
        "authorized start keeps result",
        "401 clears questionnaire subject content",
        "403 clears questionnaire subject content",
    ):
        assert label in result.stdout
