#!/usr/bin/env python3
"""외부 훈련 산출물 수령 → 검증 → (선택) MinIO · env 안내.

예 (scp 후):
  python scripts/receive_external_model.py \\
    --from-dir /path/from/gpu-server \\
    --stem retinal_v3

예 (이미 models/ 에 있을 때):
  python scripts/receive_external_model.py --stem retinal_v3 --skip-copy
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    p = argparse.ArgumentParser(description="외부 훈련 모델 수령 파이프라인")
    p.add_argument("--from-dir", type=Path, help="외부 서버에서 복사한 디렉터리")
    p.add_argument("--stem", default="retinal_v3")
    p.add_argument("--models-dir", type=Path, default=ROOT / "models")
    p.add_argument("--skip-copy", action="store_true")
    p.add_argument("--upload-minio", action="store_true")
    p.add_argument("--skip-verify", action="store_true")
    args = p.parse_args()

    models_dir = args.models_dir if args.models_dir.is_absolute() else ROOT / args.models_dir
    models_dir.mkdir(parents=True, exist_ok=True)
    stem = args.stem

    if not args.skip_copy:
        if not args.from_dir:
            raise SystemExit("--from-dir required unless --skip-copy")
        src = args.from_dir if args.from_dir.is_absolute() else Path(args.from_dir)
        for ext in (".onnx", ".meta.json", ".pt"):
            s = src / f"{stem}{ext}"
            if s.is_file():
                d = models_dir / s.name
                shutil.copy2(s, d)
                print(f"copied {s} -> {d}")
            elif ext != ".pt":
                print(f"WARN missing {s}")

    if not args.skip_verify:
        rc = subprocess.call(
            [
                sys.executable,
                str(ROOT / "scripts" / "verify_external_model.py"),
                "--stem",
                stem,
                "--models-dir",
                str(models_dir),
            ],
        )
        if rc != 0:
            return rc

    onnx_name = f"{stem}.onnx"
    if args.upload_minio:
        subprocess.check_call(
            [
                sys.executable,
                str(ROOT / "training" / "deploy_model.py"),
                "--model",
                onnx_name,
                "--models-dir",
                str(models_dir),
                "--target",
                "minio",
            ],
        )

    subprocess.call(
        [
            sys.executable,
            str(ROOT / "scripts" / "download_model.py"),
            "--model",
            onnx_name,
            "--dry-run",
        ],
    )
    print("\nNext:")
    print(f"  python scripts/download_model.py --model {onnx_name}")
    print("  cd ../.. && docker compose -f docker-compose.dev.yml restart medi-iot-api")
    print("  scripts/host_fundus_partner_smoke.ps1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
