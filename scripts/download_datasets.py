#!/usr/bin/env python3
"""공개 DR 데이터셋 다운로드 (Kaggle API 또는 합성 fallback).

지원 (문서·라이선스 준수 후 수동/Kaggle):
  - APTOS 2019, Messidor-2, IDRiD, EyePACS

Kaggle API 없으면:
  - data/raw/README.md 안내 + generate_synthetic_fundus.py 로 대체
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DATASETS = {
    "aptos2019": {
        "kaggle": "aptos2019-blindness-detection",
        "url": "https://www.kaggle.com/competitions/aptos2019-blindness-detection",
        "size_gb": 9,
    },
    "messidor2": {
        "url": "https://www.adcis.net/en/third-party/messidor2/",
        "size_gb": 1.7,
        "manual": True,
    },
    "idrid": {
        "url": "https://ieee-dataport.org/open-access/indian-diabetic-retinopathy-image-dataset-idrid",
        "size_gb": 1.2,
        "manual": True,
    },
    "eyepacs": {
        "kaggle": "diabetic-retinopathy-detection",
        "url": "https://www.kaggle.com/competitions/diabetic-retinopathy-detection",
        "size_gb": 88,
    },
}


def _kaggle_available() -> bool:
    try:
        subprocess.run(
            ["kaggle", "--version"],
            check=True,
            capture_output=True,
            timeout=10,
        )
        return Path.home().joinpath(".kaggle", "kaggle.json").is_file()
    except Exception:
        return False


def _download_kaggle(slug: str, dest: Path) -> bool:
    dest.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["kaggle", "competitions", "download", "-c", slug, "-p", str(dest)],
            check=True,
            timeout=3600,
        )
        return True
    except Exception as exc:
        print(f"kaggle_fail {slug}: {exc}")
        return False


def _write_readme(raw_dir: Path) -> None:
    lines = [
        "# Raw DR datasets (not in Git)",
        "",
        "Download with Kaggle CLI (`~/.kaggle/kaggle.json`) or manual URLs:",
        "",
    ]
    for name, meta in DATASETS.items():
        lines.append(f"## {name}")
        lines.append(f"- URL: {meta['url']}")
        if meta.get("kaggle"):
            lines.append(f"- Kaggle: `kaggle competitions download -c {meta['kaggle']}`")
        lines.append("")
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def _fallback_synthetic(processed: Path, per_class: int) -> None:
    gen = ROOT / "scripts" / "generate_synthetic_fundus.py"
    subprocess.run(
        [sys.executable, str(gen), "--output", str(processed), "--per-class", str(per_class)],
        check=True,
    )
    manifest_script = ROOT / "scripts" / "build_messidor2_manifest.py"
    out_manifest = processed.parent / "synthetic_manifest.json"
    subprocess.run(
        [
            sys.executable,
            str(manifest_script),
            "--data-dir",
            str(processed),
            "--output",
            str(out_manifest),
        ],
        check=True,
    )
    print(f"OK synthetic fallback → {processed}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--dataset",
        choices=list(DATASETS.keys()) + ["all"],
        default="all",
    )
    p.add_argument("--raw-dir", type=Path, default=ROOT / "data" / "raw")
    p.add_argument("--processed-dir", type=Path, default=ROOT / "data" / "processed")
    p.add_argument("--per-class", type=int, default=200)
    p.add_argument("--force-synthetic", action="store_true")
    args = p.parse_args()

    raw = args.raw_dir if args.raw_dir.is_absolute() else ROOT / args.raw_dir
    processed = args.processed_dir if args.processed_dir.is_absolute() else ROOT / args.processed_dir
    _write_readme(raw)

    if args.force_synthetic or not _kaggle_available():
        print("Using synthetic fallback (no Kaggle API or --force-synthetic)")
        _fallback_synthetic(processed / "synthetic", args.per_class)
        return

    names = list(DATASETS.keys()) if args.dataset == "all" else [args.dataset]
    status = {}
    for name in names:
        meta = DATASETS[name]
        dest = raw / name
        if meta.get("manual"):
            status[name] = "manual_download_required"
            print(f"{name}: manual — {meta['url']}")
            continue
        slug = meta.get("kaggle")
        if slug and _download_kaggle(slug, dest):
            status[name] = "downloaded"
        else:
            status[name] = "failed"

    if not any(v == "downloaded" for v in status.values()):
        print("No Kaggle downloads succeeded — synthetic fallback")
        _fallback_synthetic(processed / "synthetic", args.per_class)

    (raw / "download_status.json").write_text(
        json.dumps(status, indent=2), encoding="utf-8"
    )
    print(f"OK status → {raw / 'download_status.json'}")


if __name__ == "__main__":
    main()
