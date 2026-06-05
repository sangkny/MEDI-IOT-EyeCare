#!/usr/bin/env python3
"""v4 vs v9_dr DR confidence 비교 (sklee 좌/우)."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def _predict(model_rel: str, image: Path) -> dict:
    import os

    os.environ["MEDI_CNN_MODEL_PATH"] = model_rel
    from services.inference_router import load_inference_config, predict_dr_from_image_bytes

    load_inference_config.cache_clear() if hasattr(load_inference_config, "cache_clear") else None
    data = image.read_bytes()
    pred = await predict_dr_from_image_bytes(data)
    return {
        "model": model_rel,
        "eye": image.stem,
        "dr_grade": pred.dr_grade,
        "confidence": round(pred.confidence, 4),
    }


async def main() -> int:
    images = [
        ROOT / "fundus_right_sklee.jpg",
        ROOT / "fundus_left_sklee.jpg",
    ]
    models = [
        "models/retinal_v4.onnx",
        "models/retinal_v9_dr.onnx",
    ]
    rows: list[dict] = []
    for img in images:
        if not img.is_file():
            print(f"skip missing {img}", file=sys.stderr)
            continue
        for m in models:
            if not (ROOT / m).is_file() and m == "models/retinal_v9_dr.onnx":
                print(f"skip missing {m}", file=sys.stderr)
                continue
            try:
                rows.append(await _predict(m, img))
            except Exception as exc:
                rows.append({"model": m, "eye": img.stem, "error": str(exc)[:120]})

    print(json.dumps(rows, indent=2, ensure_ascii=False))
    gate = 0.80
    v9_ok = all(
        r.get("confidence", 0) >= gate
        for r in rows
        if r.get("model") == "models/retinal_v9_dr.onnx" and "error" not in r
    )
    print(f"\nDeploy v9_dr if all conf >= {gate}: {v9_ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
