"""
파일명: test_glaucoma_manifest.py
목적: glaucoma manifest.py 단위·통합 테스트
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가


Glaucoma manifest 로더 단위 테스트 (Mock 0).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from training.make_manifest import (
    build_glaucoma_manifest,
    load_airogs,
    load_g1020,
    load_origa,
    load_refuge,
    load_rimone,
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


def _write_airogs_light(tmp_path: Path) -> Path:
    base = tmp_path / "Glaucoma_extra" / "airogs" / "eyepac-light-v2-512-jpg"
    for split, rg, nrg in (("train", 3, 3), ("val", 1, 1)):
        (base / split / "RG").mkdir(parents=True)
        (base / split / "NRG").mkdir(parents=True)
        for i in range(rg):
            (base / split / "RG" / f"rg_{split}_{i}.jpg").write_bytes(b"\xff\xd8\xff\xd9")
        for i in range(nrg):
            (base / split / "NRG" / f"nrg_{split}_{i}.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    return tmp_path


def _write_rimone(tmp_path: Path) -> Path:
    base = (
        tmp_path
        / "Glaucoma_extra"
        / "rimone"
        / "RIM-ONE_DL_images"
        / "partitioned_randomly"
    )
    for split, gl, nr in (("training_set", 2, 2), ("test_set", 1, 1)):
        (base / split / "glaucoma").mkdir(parents=True)
        (base / split / "normal").mkdir(parents=True)
        for i in range(gl):
            (base / split / "glaucoma" / f"g_{split}_{i}.jpg").write_bytes(b"\xff\xd8\xff\xd9")
        for i in range(nr):
            (base / split / "normal" / f"n_{split}_{i}.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    return tmp_path


def test_load_airogs_light_v2(tmp_path: Path) -> None:
    root = _write_airogs_light(tmp_path)
    extra = root / "Glaucoma_extra"
    manifest_root = root
    samples = load_airogs(
        root / "Glaucoma_raw",
        extra_root=extra,
        manifest_root=manifest_root,
    )
    assert len(samples) == 8
    assert all(s["source"] == "airogs" for s in samples)
    assert sum(1 for s in samples if s["label"] == 1) == 4
    assert all("split" in s for s in samples)


def test_load_rimone(tmp_path: Path) -> None:
    root = _write_rimone(tmp_path)
    extra = root / "Glaucoma_extra"
    samples = load_rimone(
        root / "Glaucoma_raw",
        extra_root=extra,
        manifest_root=root,
    )
    assert len(samples) == 6
    assert sum(1 for s in samples if s["split"] == "train") == 4
    assert sum(1 for s in samples if s["split"] == "test") == 2


def test_build_glaucoma_v2_extra_root(tmp_path: Path) -> None:
    raw = tmp_path / "Glaucoma_raw"
    raw.mkdir()
    _write_g1020(raw, n=4)
    _write_airogs_light(tmp_path)
    _write_rimone(tmp_path)
    out = tmp_path / "glaucoma_v2.json"
    manifest = build_glaucoma_manifest(
        raw,
        out,
        extra_root=tmp_path / "Glaucoma_extra",
        sources=("g1020", "airogs", "rimone"),
        val_ratio=0.15,
        test_ratio=0.15,
        seed=42,
        version=2,
        unified_split=True,
    )
    assert manifest["version"] == 2
    assert manifest["data_dir"] == str(tmp_path.resolve())
    assert manifest["total"] == 4 + 8 + 6
    assert "airogs" in manifest["sources"]
    assert "rimone" in manifest["sources"]
    val_samples = [s for s in manifest["samples"] if s["split"] == "val"]
    assert any(s["source"] == "airogs" for s in val_samples)
    assert sum(1 for s in val_samples if s["source"] == "airogs") >= 1
