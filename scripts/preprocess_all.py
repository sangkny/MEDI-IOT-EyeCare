"""
파일명: preprocess_all.py
목적: GL/AMD/MYO/Multi CLAHE+224 resized_cache 전처리
히스토리:
  2026-06-12 - Glaucoma_extra2 (REFUGE/G1020/ORIGA/DRISHTI) 경로 추가
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가
"""
import cv2, numpy as np
from pathlib import Path
import glob, time

clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))

src_dirs = [
    ("/dataset/Glaucoma_raw",     "/dataset/resized_cache/Glaucoma_raw"),
    ("/dataset/Glaucoma_extra",   "/dataset/resized_cache/Glaucoma_extra"),
    ("/dataset/Glaucoma_extra2/REFUGE",  "/dataset/resized_cache/Glaucoma_extra2/REFUGE"),
    ("/dataset/Glaucoma_extra2/G1020",   "/dataset/resized_cache/Glaucoma_extra2/G1020"),
    ("/dataset/Glaucoma_extra2/ORIGA",   "/dataset/resized_cache/Glaucoma_extra2/ORIGA"),
    ("/dataset/Glaucoma_extra2/DRISHTI", "/dataset/resized_cache/Glaucoma_extra2/DRISHTI"),
    ("/dataset/AMD_raw",          "/dataset/resized_cache/AMD_raw"),
    ("/dataset/Multidisease_raw", "/dataset/resized_cache/Multidisease_raw"),
]

total = 0
t0 = time.time()
for src, dst in src_dirs:
    src_path = Path(src)
    if not src_path.exists():
        print(f"없음: {src}")
        continue
    imgs = []
    for ext in ["jpg","jpeg","png"]:
        imgs += glob.glob(f"{src}/**/*.{ext}", recursive=True)
    print(f"{src}: {len(imgs)}장")
    for p in imgs:
        rel = Path(p).relative_to(src)
        out = Path(dst) / rel.with_suffix(".jpg")
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            continue
        img = cv2.imread(p)
        if img is None:
            continue
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        lab[:,:,0] = clahe.apply(lab[:,:,0])
        img = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        img = cv2.resize(img, (224,224), interpolation=cv2.INTER_LANCZOS4)
        cv2.imwrite(str(out), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        total += 1
        if total % 2000 == 0:
            print(f"{total}장 ({time.time()-t0:.0f}s, {total/(time.time()-t0):.1f}장/s)", flush=True)

print(f"완료: {total}장 ({time.time()-t0:.0f}s)")
