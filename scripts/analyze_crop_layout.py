#!/usr/bin/env python3
"""
파일명: scripts/analyze_crop_layout.py
목적:   한국인 녹내장 합본 이미지 하단 컬러 레이아웃 분석
        2분할 / 4분할 / unknown 판별 → crop_layout_analysis.json

IRB: 국내 임상기관 IRB 승인 (2019) — 로컬 전용
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import cv2

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from korean_gl_crop_utils import analyze_bottom_layout, analyze_bottom_layout_v2

IRB_INFO = {
    "institution": "Korean Clinical Institution",
    "approved_year": 2019,
    "storage_policy": "LOCAL_ONLY",
}

DEFAULT_MODIFIED = Path("/dataset/korean_fundus_input/glaucoma_modified")
DEFAULT_ORIGIN = Path("/dataset/korean_fundus_input/glaucoma_origin")
DEFAULT_OUTPUT = Path("/workspace/crop_layout_analysis.json")


def _iter_modified(input_dir: Path):
    for jpg in sorted(input_dir.glob("*.jpg"), key=lambda p: int(p.stem)):
        if jpg.stem.isdigit():
            yield str(int(jpg.stem)), jpg


def _iter_origin(input_dir: Path):
    for folder in sorted(
        [f for f in input_dir.iterdir() if f.is_dir() and f.name.isdigit()],
        key=lambda f: int(f.name),
    ):
        folder_no = int(folder.name)
        for jpg in sorted(folder.glob("*.jpg")):
            lower = jpg.name.lower()
            if any(k in lower for k in ("optic", "stereophotography", "disc", "시신경", "안저")):
                yield f"{folder_no}/{jpg.name}", jpg


def analyze_directory(
    input_dir: Path,
    *,
    source: str,
    threshold_ratio: float,
    min_distance: int = 100,
) -> dict:
    if source == "modified":
        items = list(_iter_modified(input_dir))
    else:
        items = list(_iter_origin(input_dir))

    files: list[dict] = []
    skip_log: list[dict] = []
    stats = {
        "total": 0,
        "split_2": 0,
        "split_3": 0,
        "split_4": 0,
        "unknown": 0,
        "skip": 0,
        "error": 0,
    }

    for key, path in items:
        stats["total"] += 1
        img = cv2.imread(str(path))
        if img is None:
            stats["error"] += 1
            skip_log.append({"key": key, "path": str(path), "reason": "load_failed"})
            continue

        layout = analyze_bottom_layout(
            img,
            ratio_threshold=threshold_ratio,
            min_distance=min_distance,
        )
        entry = {
            "key": key,
            "source": source,
            "path": str(path),
            **layout,
        }
        if source == "modified":
            entry["img_no"] = int(key)

        if layout["crop_possible"]:
            files.append(entry)
            if layout["layout"] == "2split":
                stats["split_2"] += 1
            elif layout["layout"] == "3split":
                stats["split_3"] += 1
            elif layout["layout"] == "4split":
                stats["split_4"] += 1
        else:
            stats["unknown"] += 1
            stats["skip"] += 1
            skip_log.append({
                "key": key,
                "path": str(path),
                "layout": layout["layout"],
                "bottom_splits": layout["bottom_splits"],
                "reason": layout.get("reason", "layout_unknown"),
            })
            files.append(entry)

    return {
        "irb": IRB_INFO,
        "analyzed_at": datetime.now().isoformat(timespec="seconds"),
        "source": source,
        "input_dir": str(input_dir),
        "threshold_ratio": threshold_ratio,
        "stats": stats,
        "files": files,
        "skip_log": skip_log,
        "policy": "crop only when layout is 2split or 4split; unknown → skip",
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input-dir", type=Path, default=None)
    p.add_argument("--source", choices=("modified", "origin"), default="modified")
    p.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--threshold-ratio", type=float, default=2.5,
                   help="gradient peak ratio vs mean (default 2.5)")
    p.add_argument("--min-distance", type=int, default=100)
    args = p.parse_args()

    input_dir = args.input_dir
    if input_dir is None:
        input_dir = DEFAULT_MODIFIED if args.source == "modified" else DEFAULT_ORIGIN

    if not input_dir.is_dir():
        print(f"error: missing {input_dir}", file=sys.stderr)
        sys.exit(1)

    result = analyze_directory(
        input_dir,
        source=args.source,
        threshold_ratio=args.threshold_ratio,
        min_distance=args.min_distance,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    st = result["stats"]
    print(f"OK {args.output_json}")
    print(f"총: {st['total']}")
    print(f"2분할: {st['split_2']}")
    print(f"3분할: {st.get('split_3', 0)}")
    print(f"4분할: {st['split_4']}")
    print(f"unknown: {st['unknown']}")
    print(f"스킵: {st['skip']}")
    if st["total"]:
        pct = st["skip"] / st["total"] * 100
        print(f"스킵 비율: {pct:.1f}%")


if __name__ == "__main__":
    main()
