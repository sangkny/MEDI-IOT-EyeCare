#!/usr/bin/env python3
"""
파일명: download_model.py
목적: download_model.py 실행 스크립트
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가

MinIO/S3에서 DR ONNX 모델 다운로드 + onnxruntime 검증 + .env 안내.

SSOT 경로: docs/model-deploy-minio.md

사용:
  python scripts/download_model.py --model retinal_v3.onnx
  python scripts/download_model.py --model retinal_v3.onnx \\
    --source minio://medi-dev/models/
  python scripts/download_model.py --model retinal_v3.onnx --dry-run
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
PROJECTS_ROOT = ROOT.parent

# MinIO SSOT (docs/model-deploy-minio.md 와 동일)
DEFAULT_BUCKET = "medi-dev"
DEFAULT_PREFIX = "models"
DEFAULT_SOURCE_URL = f"minio://{DEFAULT_BUCKET}/{DEFAULT_PREFIX}/"
DEFAULT_MODEL_V3 = "retinal_v3.onnx"


def _resolve_endpoint(cli_endpoint: str | None) -> str:
    if cli_endpoint:
        return cli_endpoint
    return (
        os.getenv("MEDI_AWS_ENDPOINT_URL")
        or os.getenv("AWS_ENDPOINT_URL")
        or "http://127.0.0.1:9000"
    )


def _resolve_credentials() -> tuple[str, str]:
    key = os.getenv("MEDI_AWS_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID") or "minioadmin"
    secret = os.getenv("MEDI_AWS_SECRET_ACCESS_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY") or "minioadmin"
    return key, secret


def _parse_minio_url(source: str) -> tuple[str, str]:
    """minio://medi-dev/models/ → (bucket, prefix)."""
    u = urlparse(source)
    if u.scheme not in ("minio", "s3"):
        raise ValueError(f"unsupported source scheme: {u.scheme}")
    bucket = u.netloc
    prefix = u.path.lstrip("/").rstrip("/")
    return bucket, prefix


def _object_keys(prefix: str, model_name: str) -> tuple[str, str]:
    stem = Path(model_name).stem
    base = prefix.rstrip("/")
    onnx_key = f"{base}/{model_name}" if base else model_name
    meta_key = f"{base}/{stem}.meta.json" if base else f"{stem}.meta.json"
    return onnx_key, meta_key


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
    onnx_key, meta_key = _object_keys(prefix, model_name)
    paths: list[Path] = []
    for key, local_name in ((onnx_key, model_name), (meta_key, f"{Path(model_name).stem}.meta.json")):
        local = dest_dir / local_name
        print(f"download s3://{bucket}/{key} -> {local}")
        s3.download_file(bucket, key, str(local))
        paths.append(local)
    return paths[0], paths[1]


def _head_exists(
    *,
    bucket: str,
    prefix: str,
    model_name: str,
    endpoint: str,
    access_key: str,
    secret_key: str,
) -> dict[str, bool]:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
    )
    onnx_key, meta_key = _object_keys(prefix, model_name)
    out: dict[str, bool] = {}
    for label, key in (("onnx", onnx_key), ("meta", meta_key)):
        try:
            s3.head_object(Bucket=bucket, Key=key)
            out[label] = True
        except ClientError:
            out[label] = False
    return out


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


def _version_from_model_name(model_name: str) -> str | None:
    m = re.match(r"retinal_(v\d+)\.onnx$", model_name, re.I)
    return m.group(1).lower() if m else None


def _upsert_env_line(text: str, key: str, value: str) -> str:
    pat = re.compile(rf"^{re.escape(key)}=.*$", re.M)
    line = f"{key}={value}"
    if pat.search(text):
        return pat.sub(line, text)
    sep = "" if text.endswith("\n") or not text else "\n"
    return text + sep + line + "\n"


def _suggest_env_update(model_name: str, meta_path: Path) -> None:
    import json

    arch = "efficientnet_b4"
    if meta_path.is_file():
        arch = json.loads(meta_path.read_text(encoding="utf-8")).get("arch", arch)
    ver = _version_from_model_name(model_name)
    candidates = [
        PROJECTS_ROOT / ".env.local",
        ROOT / ".env.local",
    ]
    for env_path in candidates:
        if not env_path.is_file():
            continue
        text = env_path.read_text(encoding="utf-8")
        if ver:
            text = _upsert_env_line(text, "MEDI_CNN_MODEL_VERSION", ver)
        text = _upsert_env_line(text, "MEDI_CNN_MODEL_PATH", f"models/{model_name}")
        text = _upsert_env_line(text, "MEDI_CNN_ARCH", arch)
        text = _upsert_env_line(text, "MEDI_CNN_AUTO_PULL", "1")
        env_path.write_text(text, encoding="utf-8")
        print(f"updated {env_path}")
        if ver:
            print(f"  MEDI_CNN_MODEL_VERSION={ver} (auto resolver uses this when PATH empty)")
        break
    else:
        print(f"hint: MEDI_CNN_MODEL_VERSION={ver or 'v3'}")
        print(f"hint: MEDI_CNN_MODEL_PATH=models/{model_name}")
        print(f"hint: MEDI_CNN_ARCH={arch}")
    print("restart: cd projects && docker compose -f docker-compose.dev.yml restart medi-iot-api")


def _print_plan(
    *,
    bucket: str,
    prefix: str,
    model_name: str,
    endpoint: str,
    dest: Path,
    exists: dict[str, bool] | None,
) -> None:
    onnx_key, meta_key = _object_keys(prefix, model_name)
    print("=== MinIO model deploy path (dry-run) ===")
    print(f"  endpoint:     {endpoint}")
    print(f"  bucket:       {bucket}")
    print(f"  prefix:       {prefix or '(root)'}")
    print(f"  onnx key:     s3://{bucket}/{onnx_key}")
    print(f"  meta key:     s3://{bucket}/{meta_key}")
    print(f"  local dest:   {dest}/")
    if exists is not None:
        print(f"  onnx exists:  {exists.get('onnx', False)}")
        print(f"  meta exists:  {exists.get('meta', False)}")
        if not exists.get("onnx"):
            print("  WARN: ONNX not in MinIO — upload with training/deploy_model.py --target minio")


def main() -> None:
    p = argparse.ArgumentParser(
        description="MinIO medi-dev/models/ 에서 DR ONNX 다운로드 (SSOT: docs/model-deploy-minio.md)",
    )
    p.add_argument("--model", default=DEFAULT_MODEL_V3, help=f"예: {DEFAULT_MODEL_V3}")
    p.add_argument(
        "--source",
        default=DEFAULT_SOURCE_URL,
        help=f"minio URL (기본 {DEFAULT_SOURCE_URL})",
    )
    p.add_argument("--dest", type=Path, default=ROOT / "models")
    p.add_argument("--bucket", default=os.getenv("MEDI_S3_BUCKET", DEFAULT_BUCKET))
    p.add_argument("--prefix", default=DEFAULT_PREFIX)
    p.add_argument("--endpoint", default=None, help="미설정 시 MEDI_AWS_ENDPOINT_URL 또는 127.0.0.1:9000")
    p.add_argument("--access-key", default=None)
    p.add_argument("--secret-key", default=None)
    p.add_argument("--skip-verify", action="store_true")
    p.add_argument("--no-env-update", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="S3 키·존재 여부만 점검")
    args = p.parse_args()

    dest = args.dest if args.dest.is_absolute() else ROOT / args.dest
    endpoint = _resolve_endpoint(args.endpoint)
    access_key, secret_key = args.access_key, args.secret_key
    if not access_key or not secret_key:
        ak, sk = _resolve_credentials()
        access_key = access_key or ak
        secret_key = secret_key or sk

    if args.source:
        bucket, prefix = _parse_minio_url(args.source)
    else:
        bucket, prefix = args.bucket, args.prefix

    if args.dry_run:
        try:
            exists = _head_exists(
                bucket=bucket,
                prefix=prefix,
                model_name=args.model,
                endpoint=endpoint,
                access_key=access_key,
                secret_key=secret_key,
            )
        except Exception as exc:
            print(f"head_check_failed: {exc}")
            exists = None
        _print_plan(
            bucket=bucket,
            prefix=prefix,
            model_name=args.model,
            endpoint=endpoint,
            dest=dest,
            exists=exists,
        )
        return

    onnx_path, meta_path = _download_s3(
        bucket=bucket,
        prefix=prefix,
        model_name=args.model,
        dest_dir=dest,
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
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
