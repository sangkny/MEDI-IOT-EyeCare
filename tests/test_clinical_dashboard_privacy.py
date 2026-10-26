"""대시보드 화면이 거절된 응답으로 이전 임상 표시를 남기지 않는지 확인한다."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

_HARNESS = Path(__file__).resolve().parent / "dashboard_privacy_harness.mjs"


def test_dashboard_clears_sensitive_panels_on_denial_and_scope_change():
    node = shutil.which("node")
    assert node, "node is required to execute the dashboard script"
    result = subprocess.run(
        [node, str(_HARNESS)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for label in (
        "401 clears sensitive content",
        "403 clears sensitive content",
        "study change clears prior subject content",
        "site change clears prior subject content",
        "subject change cannot expose stale values",
        "failed reload clears prior panels",
        "delayed response cannot repopulate revoked content",
        "valid authorized reload restores only newly authorized information",
    ):
        assert label in result.stdout
