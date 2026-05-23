#!/usr/bin/env python3
"""외부 GPU 서버에서 받은 DR 모델 번들 검증 (수령 직후).

검사:
  - models/<stem>.{onnx,meta.json} (+ 선택 .pt)
  - meta.json 필수 필드 (arch, preprocess, image_size)
  - onnxruntime 추론 스모크
  - InferenceRouter 경로 호환

사용:
  python scripts/verify_external_model.py
  python scripts/verify_external_model.py --stem retinal_v3 --models-dir models
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
REQUIRED_META = ("arch", "preprocess", "image_size", "onnx")


def main() -> int:
    p = argparse.ArgumentParser(description="외부 훈련 모델 번들 검증")
    p.add_argument("--stem", default="retinal_v3", help="예: retinal_v3 → retinal_v3.onnx")
    p.add_argument("--models-dir", type=Path, default=ROOT / "models")
    p.add_argument("--skip-onnx", action="store_true")
    args = p.parse_args()

    models_dir = args.models_dir if args.models_dir.is_absolute() else ROOT / args.models_dir
    stem = args.stem
    onnx = models_dir / f"{stem}.onnx"
    meta = models_dir / f"{stem}.meta.json"
    pt = models_dir / f"{stem}.pt"

    errors: list[str] = []
    warnings: list[str] = []

    print("=== External model bundle check ===")
    print(f"  dir:   {models_dir}")
    print(f"  stem:  {stem}")

    if not onnx.is_file():
        errors.append(f"missing {onnx}")
    else:
        print(f"  onnx:  OK ({onnx.stat().st_size // 1024} KB)")

    if not meta.is_file():
        errors.append(f"missing {meta}")
    else:
        print(f"  meta:  OK")
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"meta.json invalid: {exc}")
            data = {}
        for key in REQUIRED_META:
            if key not in data:
                errors.append(f"meta.json missing field: {key}")
        arch = data.get("arch")
        preprocess = data.get("preprocess")
        image_size = data.get("image_size")
        qwk = data.get("qwk")
        print(f"  arch={arch} preprocess={preprocess} image_size={image_size} qwk={qwk}")
        if data.get("onnx") and data.get("onnx") != onnx.name:
            warnings.append(f"meta onnx name {data.get('onnx')!r} != {onnx.name}")

    if pt.is_file():
        print(f"  pt:    OK ({pt.stat().st_size // 1024} KB)")
    else:
        warnings.append(f"optional missing {pt} (GradCAM·재학습용)")

    if not args.skip_onnx and onnx.is_file():
        try:
            import numpy as np
            import onnxruntime as ort

            sess = ort.InferenceSession(str(onnx), providers=["CPUExecutionProvider"])
            inp = sess.get_inputs()[0]
            h = w = int(data.get("image_size", 224))
            shape = inp.shape
            if len(shape) >= 4 and isinstance(shape[2], int):
                h, w = shape[2], shape[3]
            arr = np.random.randn(1, 3, h, w).astype(np.float32)
            out = sess.run(None, {inp.name: arr})[0]
            print(f"  ort:   OK output_shape={out.shape}")
        except ImportError as exc:
            warnings.append(f"onnxruntime skip: {exc}")
        except Exception as exc:
            errors.append(f"onnxruntime failed: {exc}")

    if not errors:
        try:
            import os

            os.environ["MEDI_CNN_MODEL_PATH"] = f"models/{onnx.name}"
            os.environ.pop("MEDI_CNN_MODEL_VERSION", None)
            from services.cnn_model_resolver import resolve_cnn_model

            resolved = resolve_cnn_model(app_root=ROOT)
            if resolved.absolute_path.name != onnx.name:
                warnings.append(f"resolver path {resolved.relative_path} != expected")
            else:
                print(f"  resolver: OK {resolved.relative_path} arch={resolved.arch}")
        except Exception as exc:
            warnings.append(f"resolver check: {exc}")

    for w in warnings:
        print(f"  WARN: {w}")
    for e in errors:
        print(f"  ERROR: {e}")

    if errors:
        print("\nFAIL — fix bundle before deploy")
        return 1

    print("\nPASS — safe to run:")
    print(f"  python training/deploy_model.py --model {onnx.name} --target minio")
    print(f"  python scripts/download_model.py --model {onnx.name}")
    print("  docker compose -f ../docker-compose.dev.yml restart medi-iot-api")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
