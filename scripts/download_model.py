#!/usr/bin/env python3
"""MinIO/S3에서 DR ONNX 모델 다운로드 + onnxruntime 검증 + .env 안내.

사용:
  python scripts/download_model.py --model retinal_v3.onnx
  python scripts/download_model.py --model retinal_v3.onnx \\
    --source minio://medi-dev/models/
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def _parse_minio_url(source: str) -> tuple[str, str]:
    """minio://bucket/prefix/ → (bucket, prefix)."""
    u = urlparse(source)
    if u.scheme not in ("minio", "s3"):
        raise ValueError(f"unsupported source scheme: {u.scheme}")
    bucket = u.netloc
    prefix = u.path.lstrip("/")
    return bucket, prefix


def _download_s3(
    *,
    bucket: str,
    prefix: str,
    model_name: str,
    dest_dir: Path,
    endpoint: str,
    access_key: str,
    secret_key: str,
) -> tuple[Path, Path]:
    import boto3
    from botocore.config import Config

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
    )
    dest_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(model_name).stem
    files = [model_name, f"{stem}.meta.json"]
    paths = []
    for fname in files:
        key = f"{prefix.rstrip('/')}/{fname}" if prefix else fname
        local = dest_dir / fname
        print(f"download s3://{bucket}/{key} -> {local}")
        s3.download_file(bucket, key, str(local))
        paths.append(local)
    return paths[0], paths[1]


def _verify_onnx(onnx_path: Path) -> None:
    import numpy as np
    import onnxruntime as ort

    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    inp = sess.get_inputs()[0].name
    shape = sess.get_inputs()[0].shape
    h = w = 224
    if len(shape) >= 4 and isinstance(shape[2], int):
        h, w = shape[2], shape[3]
    arr = np.random.randn(1, 3, h, w).astype(np.float32)
    out = sess.run(None, {inp: arr})[0]
    print(f"onnxruntime OK output shape={out.shape}")


def _suggest_env_update(model_name: str, meta_path: Path) -> None:
    import json

    arch = "efficientnet_b4"
    if meta_path.is_file():
        arch = json.loads(meta_path.read_text(encoding="utf-8")).get("arch", arch)
    env_local = ROOT.parent / ".env.local"
    projects_env = ROOT.parent / "projects" / ".env.local"
    for env_path in (env_local, projects_env, ROOT / ".env.local"):
        if not env_path.is_file():
            continue
        text = env_path.read_text(encoding="utf-8")
        if "MEDI_CNN_MODEL_PATH" in text:
            text = re.sub(
                r"MEDI_CNN_MODEL_PATH=.*",
                f"MEDI_CNN_MODEL_PATH=models/{model_name}",
                text,
            )
        else:
            text += f"\nMEDI_CNN_MODEL_PATH=models/{model_name}\n"
        if "MEDI_CNN_ARCH" in text:
            text = re.sub(r"MEDI_CNN_ARCH=.*", f"MEDI_CNN_ARCH={arch}", text)
        else:
            text += f"MEDI_CNN_ARCH={arch}\n"
        env_path.write_text(text, encoding="utf-8")
        print(f"updated {env_path}")
        break
    else:
        print(f"hint: set MEDI_CNN_MODEL_PATH=models/{model_name}")
        print(f"hint: set MEDI_CNN_ARCH={arch}")
    print("restart: docker compose -f projects/docker-compose.dev.yml restart medi-iot-api")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True, help="예: retinal_v3.onnx")
    p.add_argument("--source", default="", help="minio://medi-dev/models/")
    p.add_argument("--dest", type=Path, default=ROOT / "models")
    p.add_argument("--bucket", default=os.getenv("MEDI_S3_BUCKET", "medi-dev"))
    p.add_argument("--prefix", default="models")
    p.add_argument("--endpoint", default=os.getenv("MEDI_AWS_ENDPOINT_URL", "http://localhost:9000"))
    p.add_argument("--access-key", default=os.getenv("MEDI_AWS_ACCESS_KEY_ID", "minioadmin"))
    p.add_argument("--secret-key", default=os.getenv("MEDI_AWS_SECRET_ACCESS_KEY", "minioadmin"))
    p.add_argument("--skip-verify", action="store_true")
    p.add_argument("--no-env-update", action="store_true")
    args = p.parse_args()

    dest = args.dest if args.dest.is_absolute() else ROOT / args.dest

    if args.source:
        bucket, prefix = _parse_minio_url(args.source)
    else:
        bucket, prefix = args.bucket, args.prefix

    onnx_path, meta_path = _download_s3(
        bucket=bucket,
        prefix=prefix,
        model_name=args.model,
        dest_dir=dest,
        endpoint=args.endpoint,
        access_key=args.access_key,
        secret_key=args.secret_key,
    )

    if not args.skip_verify:
        try:
            _verify_onnx(onnx_path)
        except ImportError as exc:
            print(f"verify_skip (install onnxruntime): {exc}")
        except Exception as exc:
            print(f"verify_warn: {exc}")

    if not args.no_env_update:
        _suggest_env_update(args.model, meta_path)

    print("OK", onnx_path, meta_path)


if __name__ == "__main__":
    main()
