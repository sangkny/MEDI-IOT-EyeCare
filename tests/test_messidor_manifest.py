"""Messidor-2 manifest 빌더 테스트 (D R4-ML D1, Mock 0)."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import build_messidor2_manifest as bm  # noqa: E402


def _make_csv(tmp_path: Path, n: int = 20) -> Path:
    ann = tmp_path / "annotations"
    ann.mkdir(parents=True)
    img = tmp_path / "images"
    img.mkdir(parents=True)
    p = ann / "messidor_data.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=["image_id", "dr_grade", "me_grade", "laterality"]
        )
        w.writeheader()
        for i in range(n):
            name = f"img_{i:04d}.tif"
            (img / name).write_bytes(b"\x00")
            w.writerow({
                "image_id": name,
                "dr_grade": i % 5,
                "me_grade": 0,
                "laterality": "OU",
            })
    return tmp_path


def test_build_manifest_stratified_split(tmp_path: Path) -> None:
    root = _make_csv(tmp_path, n=25)
    m = bm.build_manifest(root, val_ratio=0.2, seed=42)
    assert m["version"] == 1
    assert m["stats"]["total"] == 25
    assert m["stats"]["train"] + m["stats"]["val"] == 25
    assert len(m["train"]) == m["stats"]["train"]
    assert all("dr_grade" in e and "path" in e for e in m["train"])
    assert m["stats"]["missing_files"] == 0


def test_main_writes_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _make_csv(tmp_path, n=10)
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
            "--val-ratio",
            "0.3",
        ],
    )
    assert bm.main() == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["stats"]["total"] == 10
    assert data["split"]["val_ratio"] == 0.3
