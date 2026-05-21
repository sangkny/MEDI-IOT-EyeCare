#!/usr/bin/env python3
"""데이터셋 준비 — 합성 / Kaggle / manifest."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--mode",
        choices=["synthetic", "download", "manifest"],
        default="synthetic",
    )
    p.add_argument("--per-class", type=int, default=200)
    p.add_argument("--data-dir", type=Path, default=ROOT / "data" / "synthetic")
    p.add_argument("--manifest-out", type=Path, default=ROOT / "data" / "synthetic_manifest.json")
    p.add_argument("--dataset", default="all", help="download 모드: aptos2019|messidor2|all")
    p.add_argument("--force-synthetic", action="store_true")
    args = p.parse_args()

    py = sys.executable

    if args.mode == "synthetic":
        subprocess.run(
            [py, str(ROOT / "scripts" / "generate_synthetic_fundus.py"),
             "--output", str(args.data_dir), "--per-class", str(args.per_class)],
            check=True,
        )
        args.mode = "manifest"

    if args.mode == "download":
        cmd = [py, str(ROOT / "scripts" / "download_datasets.py"), "--processed-dir", str(args.data_dir.parent)]
        if args.force_synthetic:
            cmd.append("--force-synthetic")
        if args.dataset != "all":
            cmd.extend(["--dataset", args.dataset])
        subprocess.run(cmd, check=True)
        return

    if args.mode == "manifest":
        subprocess.run(
            [
                py,
                str(ROOT / "scripts" / "build_messidor2_manifest.py"),
                "--data-dir",
                str(args.data_dir),
                "--output",
                str(args.manifest_out),
            ],
            check=True,
        )
        print(f"OK manifest {args.manifest_out}")


if __name__ == "__main__":
    main()
