#!/usr/bin/env python3
"""
파일명: e2e_fundus_smoke.py
목적: e2e_fundus_smoke.py 실행 스크립트
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가

안저·영상·파트너 API 스모크 (컨테이너/로컬).
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

NORMAL_URL = (
    "https://upload.wikimedia.org/wikipedia/commons/3/3b/"
    "Fundus_photograph_of_normal_right_eye.jpg"
)
DR_URL = (
    "https://upload.wikimedia.org/wikipedia/commons/c/c0/"
    "Fundus_photo_showing_diabetic_retinopathy_EDA09.JPG"
)

# HTTP 스모크: 컨테이너 exec 기본 → 호스트 published :8001
# 호스트 직접 실행: MEDI_API_URL=http://localhost:8001 python3 scripts/e2e_fundus_smoke.py
API_URL = os.getenv("MEDI_API_URL", "http://host.docker.internal:8001")


def _download(url: str, dest: Path) -> None:
    import urllib.request

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "MEDI-IOT-EyeCare/1.0 (smoke-test)"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        dest.write_bytes(resp.read())


def _synthetic_fundus_jpeg(dest: Path, *, seed: int = 0) -> None:
    """네트워크 없이 스모크용 원형 안저 패턴 JPEG 생성."""
    import numpy as np
    from PIL import Image, ImageDraw

    rng = np.random.default_rng(seed)
    img = rng.integers(20, 60, (512, 512, 3), dtype=np.uint8)
    pil = Image.fromarray(img, mode="RGB")
    draw = ImageDraw.Draw(pil)
    cx, cy, r = 256, 256, 200
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(120, 40, 40))
    draw.ellipse((cx - 30, cy - 30, cx + 30, cy + 30), fill=(30, 30, 30))
    pil.save(dest, format="JPEG", quality=92)


def _ensure_image(path: Path, url: str, *, seed: int) -> None:
    if path.is_file() and path.stat().st_size > 1000:
        return
    try:
        _download(url, path)
    except Exception:
        _synthetic_fundus_jpeg(path, seed=seed)


def _truncate_b64(obj: dict, key: str = "heatmap_base64", head: int = 80) -> dict:
    out = dict(obj)
    if key in out and out[key]:
        s = out[key]
        out[key] = f"{s[:head]}...({len(s)} chars)"
    return out


async def main() -> None:
    from services.cnn_model_resolver import resolve_cnn_model

    os.environ.setdefault("MEDI_INFERENCE_BACKEND", "cnn")
    resolved = resolve_cnn_model(app_root=ROOT)
    print("cnn_model", resolved.relative_path, f"version={resolved.version} source={resolved.source}")

    tmp = Path("/tmp")
    normal = tmp / "test_fundus_normal.jpg"
    dr = tmp / "test_fundus_dr.jpg"

    print("=== Step 2: 이미지 다운로드 ===")
    for path, url, seed in (
        (normal, NORMAL_URL, 42),
        (dr, DR_URL, 7),
    ):
        _ensure_image(path, url, seed=seed)
        print("OK", path, path.stat().st_size, "bytes", "(synthetic)" if seed == 7 and path == dr else "")

    print("\n=== Step 1 확인: ONNX ===")
    onnx = resolved.absolute_path
    meta = onnx.with_suffix(".meta.json")
    print("onnx", onnx.is_file(), onnx.stat().st_size if onnx.is_file() else 0)
    if meta.is_file():
        print("meta", meta.read_text(encoding="utf-8")[:300])

    print("\n=== Step 4: CNN InferenceRouter ===")
    from services.inference_router import analyze_image_via_router

    res = await analyze_image_via_router(str(normal), "fundus")
    print(
        json.dumps(
            {
                "dr_grade": getattr(res, "condition", None),
                "condition_kr": res.condition_kr,
                "confidence": res.confidence,
                "icd10_code": res.icd10_code,
                "severity": res.severity,
                "model_used": res.model_used,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    try:
        import torch

        print("cuda_available", torch.cuda.is_available())
    except Exception as exc:
        print("torch_cuda_skip", exc)

    print("\n=== Step 6: GradCAM ===")
    from services.gradcam import GradCAMVisualizer

    img_bytes = normal.read_bytes()
    heat = await GradCAMVisualizer().generate_heatmap(img_bytes)
    print("heatmap_base64", f"{heat[:80]}...({len(heat)} chars)")

    print("\n=== Step 7: Video DR ===")
    try:
        import cv2
        import numpy as np

        img = cv2.imread(str(normal))
        mp4 = tmp / "test_fundus.mp4"
        if img is not None:
            h, w = img.shape[:2]
            out = cv2.VideoWriter(
                str(mp4), cv2.VideoWriter_fourcc(*"mp4v"), 5, (w, h)
            )
            for _ in range(15):
                out.write(img)
            out.release()
            print("video", mp4, mp4.stat().st_size)
        from services.fundus_video import (
            aggregate_dr_predictions,
            extract_jpeg_frames_from_video,
        )
        from services.inference_router import predict_dr_from_image_bytes

        raw = mp4.read_bytes()
        frames = extract_jpeg_frames_from_video(raw, max_frames=5, target_fps=0.25)
        preds = []
        for j in frames:
            preds.append(await predict_dr_from_image_bytes(j))
        agg = aggregate_dr_predictions(preds)
        from services.retinal_cnn import dr_prediction_to_parsed

        print("video_aggregate", json.dumps(dr_prediction_to_parsed(agg), ensure_ascii=False))
    except Exception as exc:
        print("video_skip", exc)

    print(f"\n=== Step 3/5: HTTP ({API_URL}) ===")
    base = API_URL.rstrip("/")
    try:
        import httpx

        async with httpx.AsyncClient(timeout=120.0) as client:
            h = await client.get(f"{base}/health")
            print("health", h.status_code, h.text[:120])

            with normal.open("rb") as f:
                r = await client.post(
                    f"{base}/api/v1/lab/fundus/comprehensive",
                    files={"file": ("normal.jpg", f, "image/jpeg")},
                    data={
                        "lang": "ko",
                        "lat": "37.5665",
                        "lng": "126.9780",
                        "include_heatmap": "true",
                    },
                )
            if r.status_code == 200:
                body = r.json()
                print(
                    "comprehensive",
                    json.dumps(_truncate_b64(body), ensure_ascii=False, indent=2)[:4000],
                )
            else:
                print("comprehensive_fail", r.status_code, r.text[:500])

            if (tmp / "test_fundus.mp4").is_file():
                with (tmp / "test_fundus.mp4").open("rb") as vf:
                    vr = await client.post(
                        f"{base}/api/v1/lab/video-dr/analyze",
                        files={"file": ("test.mp4", vf, "video/mp4")},
                        data={"max_frames": "5"},
                    )
                print(
                    "video_dr",
                    vr.status_code,
                    vr.text[:2000] if vr.status_code == 200 else vr.text[:400],
                )

            b64 = base64.b64encode(normal.read_bytes()).decode()
            import time

            smoke_pid = f"smoke-lab-{int(time.time())}"
            reg = await client.post(
                f"{base}/api/v1/partner/register",
                json={
                    "partner_id": smoke_pid,
                    "name": "Smoke Lab Partner",
                    "plan": "trial",
                },
            )
            if reg.status_code == 201:
                api_key = reg.json()["api_key"]
                pa = await client.post(
                    f"{base}/api/v1/partner/analyze",
                    headers={"X-API-Key": api_key},
                    json={
                        "partner_id": smoke_pid,
                        "image_base64": b64,
                        "return_format": "json",
                        "include_heatmap": True,
                        "lang": "ko",
                    },
                )
                if pa.status_code == 200:
                    print(
                        "partner_analyze",
                        json.dumps(_truncate_b64(pa.json()), ensure_ascii=False, indent=2),
                    )
                else:
                    print("partner_analyze_fail", pa.status_code, pa.text[:400])
            elif reg.status_code == 409:
                print("partner_register_skip", reg.text[:200])
            else:
                print("partner_register", reg.status_code, reg.text[:300])
    except Exception as exc:
        print("http_skip", exc)


if __name__ == "__main__":
    asyncio.run(main())
