#!/usr/bin/env python3
"""unified_v10e.json v2_cache 경로 검증 (GPU/Docker 실행)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "training/manifests/unified_v10e.json",
    )
    args = p.parse_args()
    path = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
    if not path.is_file():
        raise SystemExit(f"FAIL: manifest not found: {path}")

    m = json.loads(path.read_text(encoding="utf-8"))
    samples = m.get("samples") or []
    dr = [s for s in samples if "dr" in (s.get("available_labels") or {})]
    gl = [s for s in samples if "glaucoma" in (s.get("available_labels") or {})]
    if not dr or not gl:
        raise SystemExit("FAIL: DR or GL samples missing")

    dr_path = dr[0]["path"]
    gl_path = gl[0]["path"]
    dr_v2 = sum(1 for s in dr if "v2_cache" in s["path"])
    gl_v2 = sum(1 for s in gl if "v2_cache" in s["path"])

    print(f"total:     {m.get('total', len(samples))}")
    print(f"DR 첫 경로: {dr_path}")
    print(f"GL 첫 경로: {gl_path}")
    print(f"v2_cache DR: {dr_v2}/{len(dr)}")
    print(f"v2_cache GL: {gl_v2}/{len(gl)}")

    ok = "v2_cache" in dr_path and "v2_cache" in gl_path
    if not ok:
        print("WARN: v2_cache 미포함 — EXTRA2_V2=1 bash scripts/run_build_v10e_manifest_gpu.sh")
        sys.exit(1)
    print("OK: v2_cache paths verified")


if __name__ == "__main__":
    main()
