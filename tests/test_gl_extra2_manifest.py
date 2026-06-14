"""
목적: build_gl_extra2_manifest 라벨 파싱 단위 테스트
히스토리:
  2026-06-13 - 최초 작성
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_gl_extra2_manifest as gl_extra2  # noqa: E402

parse_g1020 = gl_extra2.parse_g1020
parse_origa = gl_extra2.parse_origa
parse_acrima = gl_extra2.parse_acrima

pytestmark = pytest.mark.unit


def _write_g1020(root: Path) -> None:
    base = root / "Glaucoma_extra2/G1020/G1020"
    img_dir = base / "Images"
    img_dir.mkdir(parents=True)
    (img_dir / "image_0.jpg").write_bytes(b"\xff\xd8\xff")
    (img_dir / "image_1.jpg").write_bytes(b"\xff\xd8\xff")
    with (base / "G1020.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["imageID", "binaryLabels"])
        w.writerow(["image_0.jpg", "0"])
        w.writerow(["image_1.jpg", "1"])


def _write_origa(root: Path) -> None:
    base = root / "Glaucoma_extra2/G1020/ORIGA"
    img_dir = base / "Images"
    img_dir.mkdir(parents=True)
    (img_dir / "001.jpg").write_bytes(b"\xff\xd8\xff")
    with (base / "OrigaList.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Filename", "Glaucoma"])
        w.writerow(["001.jpg", "1"])


def _write_acrima(root: Path) -> None:
    img_dir = root / "Glaucoma_extra2/ORIGA/ACRIMA/Images"
    img_dir.mkdir(parents=True)
    (img_dir / "normal_001.jpg").write_bytes(b"\xff\xd8\xff")
    (img_dir / "case_g_002.jpg").write_bytes(b"\xff\xd8\xff")


def test_parse_g1020_origa_acrima(tmp_path: Path) -> None:
    _write_g1020(tmp_path)
    _write_origa(tmp_path)
    _write_acrima(tmp_path)

    g_samples, g_stats = parse_g1020(tmp_path, path_root="Glaucoma_extra2")
    o_samples, o_stats = parse_origa(tmp_path, path_root="Glaucoma_extra2")
    a_samples, a_stats = parse_acrima(tmp_path, path_root="Glaucoma_extra2")

    assert g_stats.total == 2
    assert g_stats.normal == 1 and g_stats.abnormal == 1
    assert o_stats.total == 1 and o_stats.abnormal == 1
    assert a_stats.total == 2
    assert a_stats.normal == 1 and a_stats.abnormal == 1

    by_name = {Path(s["path"]).name: s for s in a_samples}
    assert by_name["case_g_002.jpg"]["available_labels"]["glaucoma"] == 1
    assert by_name["normal_001.jpg"]["available_labels"]["glaucoma"] == 0
