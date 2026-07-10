#!/usr/bin/env python3
"""한국인 GL 크롭 결과 HTML 검증 페이지 생성."""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

import cv2
import numpy as np

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

DEFAULT_INPUT = Path("/dataset/korean_fundus_input/glaucoma_modified")
DEFAULT_CROPS = Path("/dataset/korean_glaucoma_fundus/modified")
DEFAULT_LAYOUT = _ROOT / "crop_layout_analysis.json"
DEFAULT_OUT = _ROOT / "inspect_korean_gl_crops.html"
HIGHLIGHT = [1, 3, 6, 19]


def _b64_jpeg(img: np.ndarray, quality: int = 85) -> str:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        return ""
    return base64.b64encode(buf.tobytes()).decode("ascii")


def _draw_boxes(img: np.ndarray, entry: dict) -> np.ndarray:
    out = img.copy()
    split_row = int(entry.get("split_row", 0))
    h, w = out.shape[:2]
    cv2.line(out, (0, split_row), (w, split_row), (0, 255, 255), 2)
    for label, color in (("od_box", (0, 200, 0)), ("os_box", (0, 0, 255))):
        box = entry.get(label)
        if not box:
            continue
        y0, x0, y1, x1 = [int(v) for v in box]
        cv2.rectangle(out, (x0, y0), (x1, y1), color, 2)
        cv2.putText(
            out,
            label.replace("_box", "").upper(),
            (x0 + 4, max(y0 + 20, 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
        )
    return out


def _find_crop(path_dir: Path, img_no: int, eye: str, modality: str) -> Path | None:
    prefix = f"MEDI_KR_GL_modified_{img_no:04d}_{eye}_{modality}"
    matches = sorted(path_dir.glob(f"{prefix}*.jpg"))
    return matches[0] if matches else None


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    p.add_argument("--crops-dir", type=Path, default=DEFAULT_CROPS)
    p.add_argument("--layout-json", type=Path, default=DEFAULT_LAYOUT)
    p.add_argument("--output", type=Path, default=DEFAULT_OUT)
    p.add_argument("--samples", type=str, default=",".join(str(x) for x in HIGHLIGHT))
    args = p.parse_args()

    layout = json.loads(args.layout_json.read_text(encoding="utf-8"))
    by_no = {int(f["img_no"]): f for f in layout["files"] if "img_no" in f}
    stats = layout["stats"]
    samples = [int(x.strip()) for x in args.samples.split(",") if x.strip()]

    cards: list[str] = []
    for n in samples:
        entry = by_no.get(n)
        if not entry:
            continue
        src = cv2.imread(str(args.input_dir / f"{n}.jpg"))
        if src is None:
            continue
        overlay = _draw_boxes(src, entry)
        od_crop = _find_crop(args.crops_dir / "color" / "OD", n, "R", "color")
        os_crop = _find_crop(args.crops_dir / "color" / "OS", n, "L", "color")
        od_img = cv2.imread(str(od_crop)) if od_crop else None
        os_img = cv2.imread(str(os_crop)) if os_crop else None
        cards.append(
            f"""
<section class="card">
  <h2>No.{n} — {entry.get('layout')} splits={entry.get('bottom_splits')}</h2>
  <div class="row">
    <figure><figcaption>원본+박스</figcaption>
      <img src="data:image/jpeg;base64,{_b64_jpeg(cv2.resize(overlay, (750, int(750*overlay.shape[0]/overlay.shape[1]))))}"/></figure>
    <figure><figcaption>OD color</figcaption>
      <img src="data:image/jpeg;base64,{_b64_jpeg(od_img) if od_img is not None else ''}"/></figure>
    <figure><figcaption>OS color</figcaption>
      <img src="data:image/jpeg;base64,{_b64_jpeg(os_img) if os_img is not None else ''}"/></figure>
  </div>
</section>"""
        )

    html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"/>
<title>Korean GL Crop Inspect</title>
<style>
body {{ font-family: sans-serif; margin: 16px; background: #111; color: #eee; }}
.card {{ border: 1px solid #444; padding: 12px; margin-bottom: 20px; border-radius: 8px; }}
.row {{ display: flex; gap: 12px; flex-wrap: wrap; }}
figure {{ margin: 0; }}
img {{ max-width: 360px; border: 1px solid #666; }}
.stats {{ background: #222; padding: 12px; border-radius: 8px; margin-bottom: 20px; }}
</style></head><body>
<h1>Korean GL Crop Inspection</h1>
<div class="stats">
  <p>총 {stats['total']} — 2split={stats['split_2']} 3split={stats.get('split_3',0)} 4split={stats['split_4']} unknown={stats['unknown']}</p>
  <p>detector: gradient_v2 | analyzed: {layout.get('analyzed_at','')}</p>
</div>
{''.join(cards)}
</body></html>"""

    args.output.write_text(html, encoding="utf-8")
    print(f"OK {args.output} ({len(cards)} samples)")


if __name__ == "__main__":
    main()
