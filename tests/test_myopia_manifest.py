"""근시 manifest 로더 단위 테스트."""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from training.make_manifest import load_odir_myopia, load_rfmid_myopia

pytestmark = pytest.mark.unit


def _write_odir_fixture(root: Path) -> None:
    img_dir = root / "ODIR" / "preprocessed_images"
    img_dir.mkdir(parents=True)
    for name in (
        "m1_left.jpg",
        "m1_right.jpg",
        "n1_left.jpg",
        "n1_right.jpg",
        "d1_left.jpg",
    ):
        (img_dir / name).write_bytes(b"\xff\xd8\xff")

    csv_path = root / "ODIR" / "full_df.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["ID", "Left-Fundus", "Right-Fundus", "N", "D", "M"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "ID": "1",
                "Left-Fundus": "m1_left.jpg",
                "Right-Fundus": "m1_right.jpg",
                "N": "0",
                "D": "0",
                "M": "1",
            }
        )
        writer.writerow(
            {
                "ID": "2",
                "Left-Fundus": "n1_left.jpg",
                "Right-Fundus": "n1_right.jpg",
                "N": "1",
                "D": "0",
                "M": "0",
            }
        )
        writer.writerow(
            {
                "ID": "3",
                "Left-Fundus": "d1_left.jpg",
                "Right-Fundus": "missing.jpg",
                "N": "0",
                "D": "1",
                "M": "0",
            }
        )


def _write_rfmid_fixture(root: Path) -> None:
    train_dir = root / "RFMiD" / "Training_set"
    train_dir.mkdir(parents=True)
    (train_dir / "1.png").write_bytes(b"\x89PNG")
    (train_dir / "2.png").write_bytes(b"\x89PNG")
    (train_dir / "3.png").write_bytes(b"\x89PNG")

    csv_path = root / "RFMiD" / "Training_set" / "RFMiD_Training_Labels.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ID", "Disease_Risk", "MYA", "DR"])
        writer.writeheader()
        writer.writerow({"ID": "1.png", "Disease_Risk": "1", "MYA": "1", "DR": "0"})
        writer.writerow({"ID": "2.png", "Disease_Risk": "0", "MYA": "0", "DR": "0"})
        writer.writerow({"ID": "3.png", "Disease_Risk": "1", "MYA": "0", "DR": "1"})


def test_load_odir_myopia_strict_labels(tmp_path: Path) -> None:
    _write_odir_fixture(tmp_path)
    samples = load_odir_myopia(tmp_path, manifest_root=tmp_path)

    labels = {s["path"]: s["label"] for s in samples}
    assert labels["ODIR/preprocessed_images/m1_left.jpg"] == 1
    assert labels["ODIR/preprocessed_images/m1_right.jpg"] == 1
    assert labels["ODIR/preprocessed_images/n1_left.jpg"] == 0
    assert labels["ODIR/preprocessed_images/n1_right.jpg"] == 0
    assert "ODIR/preprocessed_images/d1_left.jpg" not in labels
    assert sum(s["label"] for s in samples) == 2
    assert len(samples) == 4


def test_load_rfmid_myopia_strict_labels(tmp_path: Path) -> None:
    _write_rfmid_fixture(tmp_path)
    samples = load_rfmid_myopia(tmp_path, manifest_root=tmp_path)

    labels = {s["path"]: s["label"] for s in samples}
    assert labels["RFMiD/Training_set/1.png"] == 1
    assert labels["RFMiD/Training_set/2.png"] == 0
    assert "RFMiD/Training_set/3.png" not in labels
    assert len(samples) == 2
