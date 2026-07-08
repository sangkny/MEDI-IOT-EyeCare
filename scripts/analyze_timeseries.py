#!/usr/bin/env python3
"""
파일명: scripts/analyze_timeseries.py
목적:   glaucoma_origin 시계열 구조 분석

IRB: 국내 임상기관 IRB 승인 (2019)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

IRB_INFO = {
    "institution": "Korean Clinical Institution",
    "approved_year": 2019,
    "storage_policy": "LOCAL_ONLY",
    "external_transfer": "PROHIBITED",
    "git_commit": "PROHIBITED",
}

DEFAULT_INPUT = Path("/dataset/korean_fundus_input/glaucoma_origin")
DEFAULT_OUTPUT = Path("/dataset/korean_glaucoma_fundus/timeseries_analysis.json")


def extract_date(fname: str) -> str:
    m = re.search(r"(\d{8})", fname)
    return m.group(1) if m else "00000000"


def parse_date(date_str: str) -> datetime | None:
    try:
        return datetime.strptime(date_str, "%Y%m%d")
    except ValueError:
        return None


def analyze(input_dir: Path) -> dict:
    folders = sorted(
        [f for f in input_dir.iterdir() if f.is_dir() and f.name.isdigit()],
        key=lambda f: int(f.name),
    )

    results: dict[int, dict] = {}
    visit_counts: dict[int, int] = defaultdict(int)
    intervals_days: list[int] = []
    multi_visit_folders: list[int] = []

    print(f"=== Timeseries analysis: {len(folders)} folders ===")
    print(f"IRB: {IRB_INFO['institution']} ({IRB_INFO['approved_year']})")
    print()

    for folder in folders:
        folder_no = int(folder.name)
        files = list(folder.glob("*.jpg"))

        dates_by_kind: dict[str, set[str]] = defaultdict(set)
        for f in files:
            date = extract_date(f.name)
            if date == "00000000":
                continue
            lower = f.name.lower()
            if any(k in lower for k in ["optic_nerve", "stereophotography", "disc", "시신경유두"]):
                dates_by_kind["fundus"].add(date)
            elif any(k in lower for k in ["sita", "visual_field", "시야"]):
                dates_by_kind["vf"].add(date)
            elif any(k in lower for k in ["oct", "rnfl", "녹내장"]):
                dates_by_kind["oct"].add(date)

        all_dates = sorted(dates_by_kind.get("fundus", set()))
        n_visits = len(all_dates)
        visit_counts[n_visits] += 1

        if n_visits >= 2:
            multi_visit_folders.append(folder_no)
            date_objs = [parse_date(d) for d in all_dates if parse_date(d)]
            for i in range(1, len(date_objs)):
                if date_objs[i] and date_objs[i - 1]:
                    intervals_days.append((date_objs[i] - date_objs[i - 1]).days)

        results[folder_no] = {
            "n_visits": n_visits,
            "dates": all_dates,
            "has_vf": len(dates_by_kind.get("vf", set())) > 0,
            "has_oct": len(dates_by_kind.get("oct", set())) > 0,
        }

        if n_visits >= 2:
            print(f"  [{folder_no:3d}] {n_visits} visits: {' -> '.join(all_dates)}")

    print()
    print("=== Visit count distribution ===")
    for n in sorted(visit_counts.keys()):
        bar = "#" * visit_counts[n]
        print(f"  {n} visits: {visit_counts[n]:3d} folders  {bar}")

    print()
    print("=== Summary ===")
    multi = sum(cnt for n, cnt in visit_counts.items() if n >= 2)
    single = visit_counts.get(1, 0)
    total = len(folders) or 1
    print(f"  Single visit: {single} ({single / total * 100:.1f}%)")
    print(f"  Multi visit:  {multi} ({multi / total * 100:.1f}%)")
    print(f"  Multi-visit folders: {len(multi_visit_folders)}")

    if intervals_days:
        avg_interval = sum(intervals_days) / len(intervals_days)
        print(f"  Avg interval: {avg_interval:.0f} days ({avg_interval / 30:.1f} months)")
        print(f"  Min interval: {min(intervals_days)} days")
        print(f"  Max interval: {max(intervals_days)} days")

    summary = {
        "irb": IRB_INFO,
        "analyzed_at": datetime.now().isoformat(),
        "total_folders": len(folders),
        "visit_count_distribution": dict(visit_counts),
        "multi_visit_folders": multi_visit_folders,
        "interval_days": {
            "count": len(intervals_days),
            "avg": sum(intervals_days) / len(intervals_days) if intervals_days else 0,
            "min": min(intervals_days) if intervals_days else None,
            "max": max(intervals_days) if intervals_days else None,
        },
        "folders": results,
    }
    return summary


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    p.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT)
    args = p.parse_args()

    if not args.input_dir.exists():
        print(f"error: missing {args.input_dir}", file=sys.stderr)
        sys.exit(1)

    summary = analyze(args.input_dir)

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\nSaved: {args.output_json}")


if __name__ == "__main__":
    main()
