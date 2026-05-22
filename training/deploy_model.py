#!/usr/bin/env python3
"""훈련 산출물 → MinIO 업로드 또는 운영 경로 안내.

SSOT: docs/model-deploy-minio.md
  s3://medi-dev/models/<model>.onnx
  s3://medi-dev/models/<stem>.meta.json
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BUCKET = "medi-dev"
DEFAULT_PREFIX = "models"


def _object_key(prefix: str, filename: str) -> str:
    base = prefix.rstrip("/")
    return f"{base}/{filename}" if base else filename


def _upload_minio(
    local: Path,
    bucket: str,
    prefix: str,
    endpoint: str,
    access_key: str,
    secret_key: str,
) -> str:
    import boto3
    from botocore.config import Config

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
    )
    key_path = _object_key(prefix, local.name)
    s3.upload_file(str(local), bucket, key_path)
    uri = f"s3://{bucket}/{key_path}"
    print(f"uploaded {uri}")
    return uri


def _resolve_endpoint(cli: str | None) -> str:
    if cli:
        return cli
    return (
        os.getenv("MEDI_AWS_ENDPOINT_URL")
        or os.getenv("AWS_ENDPOINT_URL")
        or "http://127.0.0.1:9000"
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Deploy DR model to MinIO medi-dev/models/")
    p.add_argument("--model", default="retinal_v3.onnx", help="예: retinal_v3.onnx")
    p.add_argument("--models-dir", type=Path, default=ROOT / "models")
    p.add_argument("--target", choices=["minio", "copy", "print"], default="print")
    p.add_argument("--bucket", default=os.getenv("MEDI_S3_BUCKET", DEFAULT_BUCKET))
    p.add_argument("--prefix", default=DEFAULT_PREFIX)
    p.add_argument("--endpoint", default=None)
    p.add_argument("--access-key", default=os.getenv("MEDI_AWS_ACCESS_KEY_ID", "minioadmin"))
    p.add_argument("--secret-key", default=os.getenv("MEDI_AWS_SECRET_ACCESS_KEY", "minioadmin"))
    p.add_argument("--dest", type=Path, help="copy 대상 디렉터리")
    args = p.parse_args()

    models_dir = args.models_dir if args.models_dir.is_absolute() else ROOT / args.models_dir
    stem = Path(args.model).stem
    onnx = models_dir / args.model
    meta = models_dir / f"{stem}.meta.json"
    pt = models_dir / f"{stem}.pt"
    endpoint = _resolve_endpoint(args.endpoint)

    for f in (onnx, meta):
        if not f.is_file():
            raise SystemExit(f"missing {f}")

    onnx_key = _object_key(args.prefix, onnx.name)
    meta_key = _object_key(args.prefix, meta.name)

    if args.target == "minio":
        _upload_minio(onnx, args.bucket, args.prefix, endpoint, args.access_key, args.secret_key)
        _upload_minio(meta, args.bucket, args.prefix, endpoint, args.access_key, args.secret_key)
        if pt.is_file():
            _upload_minio(pt, args.bucket, args.prefix, endpoint, args.access_key, args.secret_key)
        print(f"\nMinIO SSOT: s3://{args.bucket}/{args.prefix}/")
        print(f"  download: python scripts/download_model.py --model {onnx.name}")
    elif args.target == "copy":
        dest = args.dest or ROOT / "models"
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(onnx, dest / onnx.name)
        shutil.copy2(meta, dest / meta.name)
        if pt.is_file():
            shutil.copy2(pt, dest / pt.name)
        print(f"OK copied to {dest}")
    else:
        meta_data = json.loads(meta.read_text(encoding="utf-8"))
        print("=== Deploy checklist (retinal_v3 MinIO) ===")
        print(f"  local:        {onnx}")
        print(f"                {meta}")
        print(f"  MinIO onnx:   s3://{args.bucket}/{onnx_key}")
        print(f"  MinIO meta:   s3://{args.bucket}/{meta_key}")
        print(f"  endpoint:     {endpoint}")
        print(f"  upload:       python training/deploy_model.py --model {onnx.name} --target minio")
        print(f"  MEDI_CNN_MODEL_PATH=models/{onnx.name}")
        print(f"  MEDI_CNN_ARCH={meta_data.get('arch', 'efficientnet_b4')}")
        print("  restart: cd ../.. && docker compose -f docker-compose.dev.yml restart medi-iot-api")
        print(f"  pull:    python scripts/download_model.py --model {onnx.name} --dry-run")


if __name__ == "__main__":
    main()
