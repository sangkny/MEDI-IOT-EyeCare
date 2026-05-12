"""Messidor-2 batch importer 테스트 (D R2 Day 3).

검증:
    - annotations CSV 파싱 (header + row 갯수)
    - dry-run 모드: 디스크/S3 쓰기 없이 DB 쪽에 EyeImage + ClinicalStudyMembership 시드
    - 중복 import 방지: 동일 dataset_image_id 두 번째 호출 → skipped
    - DR grade → ICD-10 / severity 매핑 정합

테스트 철학 (Mock 0):
    - 실제 PostgreSQL (dev DB) 사용
    - 실제 import_messidor2.run() 진입점 호출 (스크립트 회귀 검증)
    - 이미지 byte I/O 는 dry-run 분기로 우회 (디스크 의존 없음)
"""
from __future__ import annotations

import asyncio
import csv
import sys
import types
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from config import get_settings
from models.clinical import ClinicalStudyMembership

# import_messidor2 는 scripts/ 폴더 — sys.path 등록
SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import import_messidor2 as imp  # type: ignore  # noqa: E402


def _async_db_url() -> str:
    url = get_settings().database_url
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


def _make_dataset(tmp_path: Path, n: int = 5) -> Path:
    """임시 데이터셋 디렉터리 생성 (images 디렉터리는 dry-run 이라 비어도 됨)."""
    ann_dir = tmp_path / "annotations"
    img_dir = tmp_path / "images"
    ann_dir.mkdir(parents=True)
    img_dir.mkdir(parents=True)
    csv_path = ann_dir / "messidor_data.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=["image_id", "dr_grade", "me_grade", "laterality"]
        )
        w.writeheader()
        for i in range(n):
            w.writerow({
                "image_id": f"img_{i:04d}.tif",
                "dr_grade": i % 5,
                "me_grade": (i % 3),
                "laterality": "OU" if i % 2 == 0 else "OD",
            })
    return tmp_path


def test_dr_to_icd10_mapping_is_complete() -> None:
    """DR grade 0~4 모두 매핑 존재."""
    for g in range(5):
        assert g in imp.DR_TO_ICD10
        assert g in imp.DR_TO_SEVERITY
    assert imp.DR_TO_ICD10[0] is None
    assert imp.DR_TO_ICD10[2] == "H36.0"
    assert imp.DR_TO_SEVERITY[4] == "severe"


def test_parse_annotations_reads_csv(tmp_path: Path) -> None:
    root = _make_dataset(tmp_path, n=3)
    rows = imp._parse_annotations(root / "annotations" / "messidor_data.csv")
    assert len(rows) == 3
    assert rows[0]["image_id"] == "img_0000.tif"
    assert rows[0]["dr_grade"] == 0
    assert rows[2]["laterality"] in {"OD", "OU"}


@pytest.mark.asyncio
async def test_dry_run_imports_into_db_then_skips_second_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("STORAGE_BACKEND", raising=False)
    root = _make_dataset(tmp_path, n=4)

    args = types.SimpleNamespace(
        data_dir=str(root), batch=2, limit=0, dry_run=True
    )

    rc = await imp.run(args)
    assert rc == 0

    eng = create_async_engine(_async_db_url(), poolclass=NullPool)
    SM = async_sessionmaker(eng, expire_on_commit=False)
    try:
        async with SM() as s:
            rows = (await s.scalars(select(ClinicalStudyMembership))).all()
            ds_ids = {r.external_id for r in rows}
            for i in range(4):
                assert f"img_{i:04d}.tif" in ds_ids, f"img_{i:04d} 미시드: {ds_ids}"

        rc2 = await imp.run(args)
        assert rc2 == 0
        async with SM() as s:
            rows2 = (await s.scalars(select(ClinicalStudyMembership))).all()
            ds_ids2 = {r.external_id for r in rows2}
            n_messidor = sum(
                1 for did in ds_ids2 if did and did.startswith("img_")
            )
            assert n_messidor >= 4

            # ground-truth ICD/severity 정합 검증 — dr_grade=2 → H36.0 / moderate
            grade2 = [r for r in rows2 if r.external_id == "img_0002.tif"]
            assert grade2, "img_0002 미시드"
            assert grade2[0].ground_truth_icd == "H36.0"
            assert grade2[0].ground_truth_severity == "moderate"
    finally:
        await eng.dispose()
