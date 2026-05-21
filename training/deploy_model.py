#!/usr/bin/env python3
"""훈련 산출물 → MinIO 업로드 또는 운영 경로 안내."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _upload_minio(local: Path, bucket: str, prefix: str, endpoint: str, key: str, secret: str) -> None:
    import boto3
    from botocore.config import Config

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=key,
        aws_secret_access_key=secret,
        config=Config(signature_version="s3v4"),
    )
    key_path = f"{prefix.rstrip('/')}/{local.name}"
    s3.upload_file(str(local), bucket, key_path)
    print(f"uploaded s3://{bucket}/{key_path}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True, help="예: retinal_v3.onnx")
    p.add_argument("--models-dir", type=Path, default=ROOT / "models")
    p.add_argument("--target", choices=["minio", "copy", "print"], default="print")
    p.add_argument("--bucket", default=os.getenv("MEDI_S3_BUCKET", "medi-dev"))
    p.add_argument("--prefix", default="models")
    p.add_argument("--endpoint", default=os.getenv("MEDI_AWS_ENDPOINT_URL", "http://localhost:9000"))
    p.add_argument("--access-key", default=os.getenv("MEDI_AWS_ACCESS_KEY_ID", "minioadmin"))
    p.add_argument("--secret-key", default=os.getenv("MEDI_AWS_SECRET_ACCESS_KEY", "minioadmin"))
    p.add_argument("--dest", type=Path, help="copy 대상 디렉터리")
    args = p.parse_args()

    models_dir = args.models_dir if args.models_dir.is_absolute() else ROOT / args.models_dir
    stem = Path(args.model).stem
    onnx = models_dir / args.model
    meta = models_dir / f"{stem}.meta.json"
    pt = models_dir / f"{stem}.pt"

    for f in (onnx, meta):
        if not f.is_file():
            raise SystemExit(f"missing {f}")

    if args.target == "minio":
        _upload_minio(onnx, args.bucket, args.prefix, args.endpoint, args.access_key, args.secret_key)
        _upload_minio(meta, args.bucket, args.prefix, args.endpoint, args.access_key, args.secret_key)
        if pt.is_file():
            _upload_minio(pt, args.bucket, args.prefix, args.endpoint, args.access_key, args.secret_key)
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
        print("=== Deploy checklist ===")
        print(f"  files: {onnx} , {meta}")
        print(f"  MEDI_CNN_MODEL_PATH=models/{onnx.name}")
        print(f"  MEDI_CNN_ARCH={meta_data.get('arch', 'efficientnet_b4')}")
        print("  docker compose -f projects/docker-compose.dev.yml restart medi-iot-api")
        print(f"  python scripts/download_model.py --model {onnx.name}")


if __name__ == "__main__":
    main()
