"""Glaucoma manifest 로더 단위 테스트 (Mock 0)."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from training.make_manifest import (
    build_glaucoma_manifest,
    load_g1020,
    load_origa,
    load_refuge,
)

pytestmark = pytest.mark.unit


def _write_g1020(tmp_path: Path, n: int = 8) -> Path:
    base = tmp_path / "G1020"
    img_dir = base / "Images"
    img_dir.mkdir(parents=True)
    with (base / "G1020.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["imageID", "binaryLabels"])
        w.writeheader()
        for i in range(n):
            image_id = f"img_{i:04d}.jpg"
            (img_dir / image_id).write_bytes(b"\xff\xd8\xff\xd9")
            w.writerow({"imageID": image_id, "binaryLabels": i % 2})
    return tmp_path


def _write_refuge(tmp_path: Path) -> Path:
    split = tmp_path / "REFUGE" / "train"
    img_dir = split / "Images"
    img_dir.mkdir(parents=True)
    (img_dir / "g001.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    (img_dir / "n001.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    index = {
        "0": {"ImgName": "g001.jpg", "Label": 1},
        "1": {"ImgName": "n001.jpg", "Label": 0},
    }
    (split / "index.json").write_text(json.dumps(index), encoding="utf-8")
    return tmp_path


def _write_origa(tmp_path: Path) -> Path:
    base = tmp_path / "ORIGA"
    img_dir = base / "Images"
    img_dir.mkdir(parents=True)
    with (base / "OrigaList.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["Eye", "Filename", "Glaucoma"])
        w.writeheader()
        w.writerow({"Eye": "L", "Filename": "o_glaucoma.jpg", "Glaucoma": 1})
        w.writerow({"Eye": "R", "Filename": "o_normal.jpg", "Glaucoma": 0})
    (img_dir / "o_glaucoma.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    (img_dir / "o_normal.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    return tmp_path


def test_load_g1020(tmp_path: Path) -> None:
    root = _write_g1020(tmp_path, n=6)
    samples = load_g1020(root)
    assert len(samples) == 6
    assert samples[0]["source"] == "g1020"
    assert "label" in samples[0]


def test_load_refuge_index_json(tmp_path: Path) -> None:
    root = _write_refuge(tmp_path)
    samples = load_refuge(root)
    assert len(samples) == 2
    assert {s["label"] for s in samples} == {0, 1}


def test_load_origa(tmp_path: Path) -> None:
    root = _write_origa(tmp_path)
    samples = load_origa(root)
    assert len(samples) == 2
    assert sum(1 for s in samples if s["label"] == 1) == 1


def test_build_glaucoma_manifest_splits(tmp_path: Path) -> None:
    root = _write_g1020(tmp_path, n=20)
    _write_refuge(root)
    _write_origa(root)
    out = tmp_path / "glaucoma_v1.json"
    manifest = build_glaucoma_manifest(
        root,
        out,
        sources=("g1020", "refuge", "origa"),
        val_ratio=0.10,
        test_ratio=0.10,
        seed=42,
    )
    assert manifest["total"] == 24
    samples = manifest["samples"]
    assert len(samples) == 24
    assert all("split" in s for s in samples)
    assert sum(1 for s in samples if s["split"] == "test") == 2  # 10%
    assert sum(1 for s in samples if s["split"] == "val") == 2  # 10%
    assert sum(1 for s in samples if s["split"] == "train") == 20  # 나머지 ~83%
    assert manifest["stats"]["glaucoma"] + manifest["stats"]["normal"] == 24
