"""
파일명: test_messidor_manifest.py
목적: messidor manifest.py 단위·통합 테스트
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가


Messidor-2 manifest 빌더 테스트 (D R4-ML D1, Mock 0).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import build_messidor2_manifest as bm  # noqa: E402


def _make_grade_image_tree(tmp_path: Path, n: int = 25) -> Path:
    """images/{0..4}/*.jpg 구조 (build_manifest 폴백 분할용)."""
    img_root = tmp_path / "images"
    for i in range(n):
        grade = i % 5
        grade_dir = img_root / str(grade)
        grade_dir.mkdir(parents=True, exist_ok=True)
        (grade_dir / f"img_{i:04d}.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    return tmp_path


def test_build_manifest_stratified_split(tmp_path: Path) -> None:
    root = _make_grade_image_tree(tmp_path, n=25)
    m = bm.build_manifest(root, source="messidor2_test")
    train = m.get("train") or []
    val = m.get("val") or []
    test = m.get("test") or []
    total = len(train) + len(val) + len(test)
    assert total == 25
    assert len(train) == 20  # 80%
    assert len(val) == 2  # 10%
    assert len(test) == 3  # 10%
    assert all("dr_grade" in e and "path" in e for e in train)


def test_main_writes_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _make_grade_image_tree(tmp_path, n=10)
    out = tmp_path / "out" / "manifest.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_messidor2_manifest.py",
            "--data-dir",
            str(root),
            "--output",
            str(out),
            "--seed",
            "42",
            "--source",
            "messidor2_test",
        ],
    )
    bm.main()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data.get("train") or []) + len(data.get("val") or []) + len(
        data.get("test") or []
    ) == 10
    assert data["source"] == "messidor2_test"
