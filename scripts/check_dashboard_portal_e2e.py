#!/usr/bin/env python3
"""
파일명: check_dashboard_portal_e2e.py
목적: check_dashboard_portal_e2e.py 실행 스크립트
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가

Dashboard Vite proxy(5174) → MEDI comprehensive Portal E2E.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
IMAGE = ROOT / "fundus_right_sklee.jpg"
import os

_BASE = os.environ.get("DASHBOARD_BASE", "http://localhost:5174")
BASE = _BASE.rstrip("/")
API = f"{BASE}/api/v1/lab/fundus/comprehensive"


def _post(mode: str) -> dict:
    if not IMAGE.is_file():
        raise SystemExit(f"FAIL: missing {IMAGE}")
    with httpx.Client(timeout=300.0) as client:
        with IMAGE.open("rb") as fh:
            r = client.post(
                API,
                params={"mode": mode},
                files={"file": ("fundus_right_sklee.jpg", fh, "image/jpeg")},
                data={
                    "patient_id": "sklee",
                    "eye_side": "OD",
                    "include_heatmap": "true",
                    "tasks": "dr,glaucoma,amd,myopia,screening",
                    "lang": "ko",
                },
            )
    r.raise_for_status()
    return r.json()


def main() -> None:
    # Dashboard dev server + proxy
    with httpx.Client(timeout=10.0) as c:
        dash = c.get(f"{BASE}/dashboard/")
        dash.raise_for_status()
        health = c.get(f"{BASE}/api/v1/health")
        health.raise_for_status()

    for mode in ("fast", "precise"):
        t0 = time.perf_counter()
        data = _post(mode)
        wall = int((time.perf_counter() - t0) * 1000)
        oa = data["overall_assessment"]
        required = ("dr", "glaucoma", "amd", "myopia", "screening")
        missing = [k for k in required if k not in data]
        if missing:
            raise SystemExit(f"FAIL {mode}: missing keys {missing}")
        print(f"=== {mode.upper()} via :5174 proxy ===")
        print("inference_mode:", oa.get("inference_mode"))
        print("inference_time_ms:", oa.get("inference_time_ms"), f"(wall {wall} ms)")
        print("primary_concern:", oa.get("primary_concern"))
        print("glaucoma:", data.get("glaucoma", {}).get("decision"))
        print("screening urgent:", data.get("screening", {}).get("urgent_diseases"))
        print()

    admin = httpx.get(f"{BASE}/dashboard/admin/models", timeout=10.0)
    admin.raise_for_status()
    if "v10c" not in admin.text and "0.8842" not in admin.text:
        print("WARN: admin page may need browser refresh for v10c card text")
    print("OK dashboard portal E2E")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
