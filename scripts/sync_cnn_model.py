#!/usr/bin/env python3
"""기동 전 CNN 모델 MinIO 동기화 (MEDI_CNN_AUTO_PULL=1).

Compose ``medi-iot-api`` command 에서 alembic 직후 실행.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = ROOT / "scripts"
for p in (str(ROOT), str(_SCRIPTS)):
    if p not in sys.path:
        sys.path.insert(0, p)

from services.cnn_model_resolver import (  # noqa: E402
    ResolvedCnnModel,
    resolve_cnn_model,
    versions_to_sync,
)

DEFAULT_SOURCE = "minio://medi-dev/models/"


def _auto_pull_enabled() -> bool:
    return (os.getenv("MEDI_CNN_AUTO_PULL") or "0").strip().lower() in ("1", "true", "yes", "on")


def _try_download(version: str, *, quiet: bool) -> bool:
    import download_model as dm

    DEFAULT_SOURCE_URL = dm.DEFAULT_SOURCE_URL
    _download_s3 = dm._download_s3
    _head_exists = dm._head_exists
    _parse_minio_url = dm._parse_minio_url
    _resolve_credentials = dm._resolve_credentials
    _resolve_endpoint = dm._resolve_endpoint

    model_name = f"retinal_{version}.onnx"
    source = (os.getenv("MEDI_CNN_MINIO_SOURCE") or DEFAULT_SOURCE_URL).strip()
    bucket, prefix = _parse_minio_url(source)
    endpoint = _resolve_endpoint(None)
    ak, sk = _resolve_credentials()
    exists = _head_exists(
        bucket=bucket,
        prefix=prefix,
        model_name=model_name,
        endpoint=endpoint,
        access_key=ak,
        secret_key=sk,
    )
    if not exists.get("onnx"):
        if not quiet:
            print(f"sync: skip {model_name} (not in MinIO)")
        return False
    dest = ROOT / "models"
    if (dest / model_name).is_file() and (dest / f"retinal_{version}.meta.json").is_file():
        if not quiet:
            print(f"sync: already local {model_name}")
        return True
    if not quiet:
        print(f"sync: pulling {model_name} from {source}")
    _download_s3(
        bucket=bucket,
        prefix=prefix,
        model_name=model_name,
        dest_dir=dest,
        endpoint=endpoint,
        access_key=ak,
        secret_key=sk,
    )
    return True


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--quiet", action="store_true", help="성공/스킵만 간단 출력")
    p.add_argument("--force", action="store_true", help="AUTO_PULL=0 이어도 실행")
    args = p.parse_args()

    os.environ.setdefault("MEDI_APP_ROOT", str(ROOT))

    if not args.force and not _auto_pull_enabled():
        if not args.quiet:
            print("sync_cnn_model: MEDI_CNN_AUTO_PULL disabled, skip")
        return 0

    resolved: ResolvedCnnModel = resolve_cnn_model(app_root=ROOT)
    if resolved.absolute_path.is_file():
        if not args.quiet:
            print(f"sync: using local {resolved.relative_path} ({resolved.source})")
        return 0

    for ver in versions_to_sync():
        try:
            if _try_download(ver, quiet=args.quiet):
                resolved = resolve_cnn_model(app_root=ROOT)
                if not args.quiet:
                    print(f"sync: ready {resolved.relative_path} version={resolved.version}")
                return 0
        except Exception as exc:
            if not args.quiet:
                print(f"sync: {ver} failed: {exc}")

    if not args.quiet:
        print(f"sync: no MinIO model; inference may use missing {resolved.relative_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
