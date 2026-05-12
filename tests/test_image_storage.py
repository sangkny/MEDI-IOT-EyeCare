"""ImageStorage 단위 테스트 (D R2 Day 3).

검증:
    - factory 가 env (``STORAGE_BACKEND``) 에 따라 올바른 backend 를 선택
    - LocalImageStorage: save/read/delete round-trip + UUID 이름
    - S3ImageStorage: boto3 미설치 시 명확한 에러 (Mock 0)
"""
from __future__ import annotations

import os
import tempfile

import pytest

from services.image_storage import (
    LocalImageStorage,
    S3ImageStorage,
    get_image_storage,
)


@pytest.fixture(autouse=True)
def _clear_storage_env(monkeypatch: pytest.MonkeyPatch):
    for k in ("STORAGE_BACKEND", "UPLOAD_DIR", "S3_BUCKET", "S3_REGION", "S3_PREFIX"):
        monkeypatch.delenv(k, raising=False)


# ── factory ──────────────────────────────────────────────


def test_factory_default_returns_local() -> None:
    s = get_image_storage()
    assert isinstance(s, LocalImageStorage)
    assert s.backend_id == "local"


def test_factory_local_with_custom_upload_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    s = get_image_storage()
    assert isinstance(s, LocalImageStorage)
    assert s.upload_dir == str(tmp_path)


def test_factory_s3_requires_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    with pytest.raises(RuntimeError, match="S3_BUCKET"):
        get_image_storage()


def test_factory_s3_with_bucket_returns_s3_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.setenv("S3_BUCKET", "medi-prod-images")
    monkeypatch.setenv("S3_REGION", "us-east-1")
    monkeypatch.setenv("S3_PREFIX", "scans/")
    s = get_image_storage()
    assert isinstance(s, S3ImageStorage)
    assert s.bucket == "medi-prod-images"
    assert s.region == "us-east-1"
    assert s.prefix == "scans/"


# ── LocalImageStorage round-trip ─────────────────────────


@pytest.mark.asyncio
async def test_local_save_read_delete_round_trip(tmp_path) -> None:
    s = LocalImageStorage(upload_dir=str(tmp_path))
    blob = b"\x89PNG\r\n\x1a\n" + b"x" * 16

    path = await s.save(blob, patient_id="P000123", filename_hint="fundus.png")
    assert path.startswith(str(tmp_path))
    assert "P000123" in path
    assert path.endswith(".png")

    fetched = await s.read(path)
    assert fetched == blob

    await s.delete(path)
    assert not os.path.exists(path)


@pytest.mark.asyncio
async def test_local_save_assigns_uuid_filename(tmp_path) -> None:
    s = LocalImageStorage(upload_dir=str(tmp_path))
    p1 = await s.save(b"a", patient_id="P0001", filename_hint="image.jpg")
    p2 = await s.save(b"b", patient_id="P0001", filename_hint="image.jpg")
    assert p1 != p2, "동일 patient 내에서도 UUID 로 충돌 회피해야 함"


# ── S3 backend (boto3 미설치 시 명확 에러) ────────────────


@pytest.mark.asyncio
async def test_s3_storage_without_boto3_raises_clear_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """``boto3`` 미설치 환경에서 ``S3ImageStorage.save`` 호출 시 RuntimeError.

    boto3 가 실제로 설치되어 있을 수 있으므로, ``sys.modules['boto3'] = None``
    트릭으로 import 를 강제 실패시켜 검증한다 (Mock 0 정신은 유지 — boto3
    네트워크 동작 시뮬레이트 없음, 단지 모듈 부재 시나리오를 재현).
    """
    import sys

    monkeypatch.setitem(sys.modules, "boto3", None)
    s = S3ImageStorage(bucket="not-real", region="us-east-1")
    with pytest.raises(RuntimeError, match="boto3"):
        await s.save(b"x", patient_id="P0001", filename_hint="x.jpg")
