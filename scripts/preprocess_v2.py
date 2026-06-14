#!/usr/bin/env python3
"""
파일명: preprocess_v2.py
목적: v2 전처리(CenterCrop+CLAHE+Unsharp)로 v2_cache 생성
      기존 resized_cache(v1 왜곡) / enhanced_cache(v1 과도) 대체
실행: Docker 컨테이너 내부에서만 실행 (docs/DOCKER-POLICY.md)
히스토리:
  2026-06-13 - 최초 작성 (fundus_enhancement v2 import)

GPU 예:
  docker run --rm --shm-size=4g \\
    -v ~/workspace/dataset:/dataset \\
    -v ~/workspace/.../MEDI-IOT-EyeCare/data:/data_dr \\
    -v ~/workspace/.../MEDI-IOT-EyeCare:/workspace \\
    --entrypoint bash medi-train:gpu -c \\
    'python3 /workspace/scripts/preprocess_v2.py'
"""
from __future__ import annotations

import glob
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402

from services.fundus_enhancement import enhance_fundus  # noqa: E402

IMAGE_SIZE = 224

SRC_DIRS = [
    ("/dataset/Glaucoma_raw", "/dataset/v2_cache/Glaucoma_raw"),
    ("/dataset/Glaucoma_extra", "/dataset/v2_cache/Glaucoma_extra"),
    ("/dataset/Glaucoma_extra2/G1020/G1020/Images", "/dataset/v2_cache/Glaucoma_extra2/G1020/G1020/Images"),
    ("/dataset/Glaucoma_extra2/G1020/ORIGA/Images", "/dataset/v2_cache/Glaucoma_extra2/G1020/ORIGA/Images"),
    ("/dataset/Glaucoma_extra2/ORIGA/ACRIMA/Images", "/dataset/v2_cache/Glaucoma_extra2/ORIGA/ACRIMA/Images"),
    ("/dataset/AMD_raw", "/dataset/v2_cache/AMD_raw"),
    ("/dataset/Multidisease_raw", "/dataset/v2_cache/Multidisease_raw"),
]

DR_SRC_DIRS = [
    ("/data_dr/aptos2019_raw", "/data_dr/v2_cache/aptos2019_raw"),
    ("/data_dr/Messidor-2_raw", "/data_dr/v2_cache/Messidor-2_raw"),
    ("/data_dr/IDRiD_raw", "/data_dr/v2_cache/IDRiD_raw"),
]


def _process_tree(src: str, dst: str) -> int:
    src_path = Path(src)
    if not src_path.exists():
        print(f"없음: {src}")
        return 0
    count = 0
    imgs: list[str] = []
    for ext in ("jpg", "jpeg", "png", "bmp", "tif", "tiff"):
        imgs.extend(glob.glob(f"{src}/**/*.{ext}", recursive=True))
        imgs.extend(glob.glob(f"{src}/**/*.{ext.upper()}", recursive=True))
    print(f"{src}: {len(imgs)}장 → {dst}")
    for p in imgs:
        rel = Path(p).relative_to(src)
        out = Path(dst) / rel.with_suffix(".jpg")
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.is_file():
            continue
        img = cv2.imread(p)
        if img is None:
            continue
        processed = enhance_fundus(img, size=IMAGE_SIZE)
        cv2.imwrite(str(out), processed, [cv2.IMWRITE_JPEG_QUALITY, 95])
        count += 1
        if count % 500 == 0:
            print(f"  {count}장 처리...", flush=True)
    return count


def main() -> None:
    t0 = time.time()
    total = 0
    for src, dst in SRC_DIRS + DR_SRC_DIRS:
        total += _process_tree(src, dst)
    print(f"완료: {total}장 ({time.time() - t0:.0f}s) v2_cache size={IMAGE_SIZE}")


if __name__ == "__main__":
    main()
