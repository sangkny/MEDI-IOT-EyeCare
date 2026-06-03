"""Glaucoma manifest 로더 단위 테스트 (Mock 0)."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from training.make_manifest import build_glaucoma_manifest, load_g1020, load_refuge2

pytestmark = pytest.mark.unit


def _write_g1020(tmp_path: Path, n: int = 8) -> Path:
    base = tmp_path / "Glaucoma_raw" / "G1020"
    img_dir = base / "Images"
    img_dir.mkdir(parents=True)
    csv_path = base / "G1020.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["image", "glaucoma"])
        w.writeheader()
        for i in range(n):
            name = f"img_{i:04d}.jpg"
            (img_dir / name).write_bytes(b"\xff\xd8\xff\xd9")
            w.writerow({"image": name, "glaucoma": i % 2})
    return tmp_path


def _write_refuge2(tmp_path: Path) -> Path:
    base = tmp_path / "Glaucoma_raw" / "REFUGE2" / "train" / "images"
    for sub, label in (("glaucoma", 1), ("normal", 0)):
        d = base / sub
        d.mkdir(parents=True)
        (d / f"{sub}_01.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    return tmp_path


def test_load_g1020(tmp_path: Path) -> None:
    root = _write_g1020(tmp_path, n=6)
    samples = load_g1020(root)
    assert len(samples) == 6
    assert all(s["task"] == "glaucoma" for s in samples)
    assert {s["glaucoma_grade"] for s in samples} <= {0, 1}


def test_load_refuge2_folder_layout(tmp_path: Path) -> None:
    root = _write_refuge2(tmp_path)
    samples = load_refuge2(root)
    assert len(samples) == 2
    assert sum(1 for s in samples if s["glaucoma_grade"] == 1) == 1


def test_build_glaucoma_manifest(tmp_path: Path) -> None:
    root = _write_g1020(tmp_path, n=10)
    _write_refuge2(root)
    out = tmp_path / "manifests" / "glaucoma_v1.json"
    manifest = build_glaucoma_manifest(root, out, val_ratio=0.2, test_ratio=0.2, seed=1)
    assert manifest["stats"]["total"] == 12
    assert out.is_file()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["task"] == "glaucoma"
    assert len(data["train"]) + len(data["val"]) + len(data["test"]) == 12
