"""Clinical Operations UI 스크립트 구문·세션 보안 하네스."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_HARNESS = Path(__file__).resolve().parent / "clinical_ops_page_harness.mjs"
_SESSION = Path(__file__).resolve().parents[1] / "static" / "clinical-ops" / "ops-session.js"
_APP = Path(__file__).resolve().parents[1] / "static" / "clinical-ops" / "ops-app.js"

pytestmark = pytest.mark.unit


def test_clinical_ops_scripts_exist_and_avoid_localstorage() -> None:
    assert _SESSION.is_file()
    assert _APP.is_file()
    session = _SESSION.read_text(encoding="utf-8")
    app = _APP.read_text(encoding="utf-8")
    assert "localStorage.getItem" not in session and "localStorage.setItem" not in session
    assert "localStorage.getItem" not in app and "localStorage.setItem" not in app
    assert "sessionStorage.setItem" not in session
    assert "Bearer" in session
    assert "clearSensitive" in session


def test_clinical_ops_harness() -> None:
    node = shutil.which("node")
    assert node, "node is required"
    result = subprocess.run(
        [node, str(_HARNESS)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for label in (
        "clinical-ops scripts parse",
        "memory-only session constraints",
        "ClinicalOpsSession registered",
        "ops-app handlers registered",
        "401 clears sensitive session",
        "403 clears sensitive session",
        "stale response protection",
    ):
        assert label in result.stdout
