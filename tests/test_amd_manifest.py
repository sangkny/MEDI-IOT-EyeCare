"""AMD manifest 로더 단위 테스트 (Mock 0, fixture 기반)."""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from training.make_manifest import (
    build_amd_manifest,
    load_amdnet23,
    load_odir_amd,
    load_rfmid_amd,
)

pytestmark = pytest.mark.unit


def _write_amdnet23(tmp_path: Path) -> Path:
    amd_raw = tmp_path / "AMD_raw"
    dataset = amd_raw / "AMDNet23" / "AMDNet23 Dataset"
    for split, amd_n, normal_n in (("train", 3, 2), ("valid", 1, 1)):
        (dataset / split / "amd").mkdir(parents=True)
        (dataset / split / "normal").mkdir(parents=True)
        for i in range(amd_n):
            (dataset / split / "amd" / f"a_{split}_{i}.jpg").write_bytes(b"\xff\xd8\xff\xd9")
        for i in range(normal_n):
            (dataset / split / "normal" / f"n_{split}_{i}.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    return amd_raw


def _write_odir_amd(tmp_path: Path) -> Path:
    odir = tmp_path / "Multidisease_raw" / "ODIR"
    img_dir = odir / "preprocessed_images"
    img_dir.mkdir(parents=True)
    rows = [
        {"ID": "amd1.jpg", "N": 0, "A": 1},
        {"ID": "amd2.jpg", "N": 0, "A": 1},
        {"ID": "norm1.jpg", "N": 1, "A": 0},
        {"ID": "norm2.jpg", "N": 1, "A": 0},
        {"ID": "dr_only.jpg", "N": 0, "A": 0, "D": 1},
    ]
    with (odir / "full_df.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ID", "N", "D", "A"])
        writer.writeheader()
        writer.writerows(rows)
    for row in rows[:4]:
        (img_dir / row["ID"]).write_bytes(b"\xff\xd8\xff\xd9")
    return tmp_path / "Multidisease_raw"


def _write_rfmid_amd(tmp_path: Path) -> Path:
    base = tmp_path / "Multidisease_raw" / "RFMiD" / "Training_set"
    base.mkdir(parents=True)
    rows = [
        {"ID": "1", "Disease_Risk": 1, "ARMD": 1, "MYA": 0},
        {"ID": "2", "Disease_Risk": 0, "ARMD": 0, "MYA": 0},
        {"ID": "3", "Disease_Risk": 1, "ARMD": 0, "MYA": 1},
    ]
    with (base / "RFMiD_Training_Labels.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ID", "Disease_Risk", "ARMD", "MYA"])
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        (base / f"{row['ID']}.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    return tmp_path / "Multidisease_raw"


def test_load_amdnet23(tmp_path: Path) -> None:
    amd_raw = _write_amdnet23(tmp_path)
    samples = load_amdnet23(amd_raw, manifest_root=tmp_path)
    assert len(samples) == 7
    assert samples[0]["source"] == "amdnet23"
    assert samples[0]["task"] == "amd"
    assert sum(1 for s in samples if s["label"] == 1) == 4
    assert sum(1 for s in samples if s["label"] == 0) == 3
    assert all(s["path"].startswith("AMD_raw/") for s in samples)


def test_load_odir_amd(tmp_path: Path) -> None:
    extra = _write_odir_amd(tmp_path)
    samples = load_odir_amd(extra, manifest_root=tmp_path)
    assert len(samples) == 4
    assert {s["label"] for s in samples} == {0, 1}
    assert all(s["source"] == "odir_amd" for s in samples)


def test_load_rfmid_amd(tmp_path: Path) -> None:
    extra = _write_rfmid_amd(tmp_path)
    samples = load_rfmid_amd(extra, manifest_root=tmp_path)
    assert len(samples) == 2
    assert sum(1 for s in samples if s["label"] == 1) == 1
    assert sum(1 for s in samples if s["label"] == 0) == 1


def test_build_amd_manifest_unified_split(tmp_path: Path) -> None:
    amd_raw = _write_amdnet23(tmp_path)
    extra = _write_odir_amd(tmp_path)
    _write_rfmid_amd(tmp_path)
    out = tmp_path / "amd_v1.json"
    manifest = build_amd_manifest(
        amd_raw,
        out,
        extra_root=extra,
        sources=("amdnet23", "odir_amd", "rfmid_amd"),
        val_ratio=0.15,
        test_ratio=0.15,
        seed=42,
    )
    assert manifest["total"] == 13
    assert manifest["data_dir"] == str(tmp_path.resolve())
    samples = manifest["samples"]
    assert len(samples) == 13
    assert all("split" in s for s in samples)
    assert sum(1 for s in samples if s["label"] == 1) == 7
    assert sum(1 for s in samples if s["label"] == 0) == 6
