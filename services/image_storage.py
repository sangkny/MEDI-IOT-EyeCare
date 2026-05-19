"""MEDI 이미지 저장 백엔드 추상화 (D R2 Day 3).

환경변수:
    - ``STORAGE_BACKEND=local|s3`` (기본 ``local``)
    - local: ``UPLOAD_DIR`` (기본 ``/app/uploads``)
    - s3:    ``S3_BUCKET``, ``S3_REGION``, ``S3_PREFIX`` (기본 ``medi/``),
             ``AWS_ACCESS_KEY_ID``, ``AWS_SECRET_ACCESS_KEY`` 또는 IAM role.

설계 결정:
    - ``boto3`` 는 lazy import — 미설치 + STORAGE_BACKEND!=s3 환경에서는 영향 없음.
    - ``LocalImageStorage`` 는 기존 ``/app/uploads`` 동작을 그대로 유지 (회귀 없음).
    - ``S3ImageStorage`` 는 ``s3://bucket/key`` 형태의 ``file_path`` 를 반환하고,
      읽기 시점에 boto3 가 byte 를 fetch 한다 (FileResponse 와의 호환은 별도).
    - 단위 테스트는 ``StorageBackend`` factory 만 검증 — boto3 실호출 없음.
"""
from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

log = logging.getLogger("services.image_storage")

_STORAGE_OPS = None


def _inc_storage_op(backend: str, operation: str = "save") -> None:
    """``medi_storage_operations_total{backend,operation}`` (D R3 D5, best-effort)."""
    global _STORAGE_OPS
    try:
        from prometheus_client import Counter

        if _STORAGE_OPS is None:
            _STORAGE_OPS = Counter(
                "medi_storage_operations_total",
                "MEDI image storage operations",
                ["backend", "operation"],
            )
        _STORAGE_OPS.labels(backend=backend, operation=operation).inc()
    except Exception:
        pass


# ── 공통 인터페이스 ────────────────────────────────────────


class ImageStorage(Protocol):
    backend_id: str

    async def save(self, data: bytes, *, patient_id: str, filename_hint: str) -> str:
        """원본 byte 를 저장하고 ``file_path`` (도메인 식별자) 를 반환."""

    async def read(self, file_path: str) -> bytes:
        """저장된 file_path 의 byte 를 반환."""

    async def delete(self, file_path: str) -> None:
        """저장된 파일을 삭제 (best-effort)."""


# ── Local backend ─────────────────────────────────────────


@dataclass
class LocalImageStorage:
    upload_dir: str = "/app/uploads"
    backend_id: str = "local"

    def _ensure_patient_dir(self, patient_id: str) -> Path:
        d = Path(self.upload_dir) / patient_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    async def save(
        self, data: bytes, *, patient_id: str, filename_hint: str
    ) -> str:
        patient_dir = self._ensure_patient_dir(patient_id)
        ext = Path(filename_hint or "upload.jpg").suffix or ".jpg"
        name = f"{uuid.uuid4().hex}{ext}"
        path = patient_dir / name
        path.write_bytes(data)
        _inc_storage_op(self.backend_id, "save")
        return str(path)

    async def read(self, file_path: str) -> bytes:
        return Path(file_path).read_bytes()

    async def delete(self, file_path: str) -> None:
        Path(file_path).unlink(missing_ok=True)


# ── S3 backend (lazy boto3) ───────────────────────────────


@dataclass
class S3ImageStorage:
    bucket: str
    region: str = "ap-northeast-2"
    prefix: str = "medi/"
    backend_id: str = "s3"

    def _key_for(self, *, patient_id: str, filename_hint: str) -> str:
        ext = Path(filename_hint or "upload.jpg").suffix or ".jpg"
        return f"{self.prefix.rstrip('/')}/{patient_id}/{uuid.uuid4().hex}{ext}"

    def _client(self) -> Any:
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError(
                "STORAGE_BACKEND=s3 인데 boto3 가 설치되어 있지 않습니다. "
                "`pip install boto3` 또는 STORAGE_BACKEND=local 로 전환하세요."
            ) from exc
        endpoint = (os.getenv("AWS_ENDPOINT_URL") or "").strip() or None
        kwargs: dict[str, Any] = {"region_name": self.region}
        if endpoint:
            kwargs["endpoint_url"] = endpoint
        return boto3.client("s3", **kwargs)

    async def save(
        self, data: bytes, *, patient_id: str, filename_hint: str
    ) -> str:
        key = self._key_for(patient_id=patient_id, filename_hint=filename_hint)
        cli = self._client()
        cli.put_object(Bucket=self.bucket, Key=key, Body=data)
        _inc_storage_op(self.backend_id, "save")
        return f"s3://{self.bucket}/{key}"

    async def read(self, file_path: str) -> bytes:
        if not file_path.startswith("s3://"):
            raise ValueError(f"S3 backend 에서 비표준 경로: {file_path!r}")
        _, _, rest = file_path.partition("s3://")
        bucket, _, key = rest.partition("/")
        cli = self._client()
        obj = cli.get_object(Bucket=bucket, Key=key)
        return obj["Body"].read()

    async def delete(self, file_path: str) -> None:
        if not file_path.startswith("s3://"):
            return
        _, _, rest = file_path.partition("s3://")
        bucket, _, key = rest.partition("/")
        try:
            self._client().delete_object(Bucket=bucket, Key=key)
        except Exception:
            pass


# ── factory ────────────────────────────────────────────────


def get_image_storage() -> ImageStorage:
    """``STORAGE_BACKEND`` env 토글 기반 storage 인스턴스 반환.

    - ``local`` (기본) → ``LocalImageStorage(upload_dir=UPLOAD_DIR or /app/uploads)``
    - ``s3``           → ``S3ImageStorage(bucket=S3_BUCKET, ...)``
    """
    backend = os.getenv("STORAGE_BACKEND", "local").strip().lower()
    if backend == "s3":
        bucket = os.getenv("S3_BUCKET", "").strip()
        if not bucket:
            raise RuntimeError(
                "STORAGE_BACKEND=s3 인데 S3_BUCKET 환경변수가 비어있습니다."
            )
        return S3ImageStorage(
            bucket=bucket,
            region=os.getenv("S3_REGION", "ap-northeast-2"),
            prefix=os.getenv("S3_PREFIX", "medi/"),
        )
    return LocalImageStorage(
        upload_dir=os.getenv("UPLOAD_DIR", "/app/uploads"),
    )


__all__ = [
    "ImageStorage",
    "LocalImageStorage",
    "S3ImageStorage",
    "get_image_storage",
]
