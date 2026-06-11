#!/usr/bin/env python3
"""
파일명: check_comprehensive_modes_e2e.py
목적: check_comprehensive_modes_e2e.py 실행 스크립트
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가

fast/precise comprehensive API E2E — sklee 우안.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
IMAGE = ROOT / "fundus_right_sklee.jpg"
API = "http://localhost:8001/api/v1/lab/fundus/comprehensive"


def run(mode: str) -> dict:
    if not IMAGE.is_file():
        raise SystemExit(f"FAIL: missing {IMAGE}")
    with httpx.Client(timeout=300.0) as client:
        with IMAGE.open("rb") as fh:
            r = client.post(
                API,
                params={"mode": mode},
                files={"file": ("fundus_right_sklee.jpg", fh, "image/jpeg")},
                data={"patient_id": "sklee", "eye": "right"},
            )
    r.raise_for_status()
    return r.json()


def main() -> None:
    for mode in ("fast", "precise"):
        t0 = time.perf_counter()
        data = run(mode)
        wall = int((time.perf_counter() - t0) * 1000)
        oa = data["overall_assessment"]
        gl = data.get("glaucoma") or {}
        print(f"=== {mode.upper()} ===")
        print("inference_mode:", oa.get("inference_mode"))
        print("inference_time_ms:", oa.get("inference_time_ms"), "(wall", wall, "ms)")
        print("primary_concern:", oa.get("primary_concern"))
        print("GL prob:", gl.get("probability"), "decision:", gl.get("decision"))
        print()
    print("OK")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
