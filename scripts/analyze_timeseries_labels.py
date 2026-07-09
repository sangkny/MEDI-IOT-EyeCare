#!/usr/bin/env python3
"""
파일명: scripts/analyze_timeseries_labels.py
목적:   timeseries_labels.csv 정밀 분석 (STEP 0)

IRB: 국내 임상기관 IRB 승인 (2019) — 로컬 전용
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

DEFAULT_CSV = Path("/dataset/korean_glaucoma_fundus/timeseries_labels.csv")
DEFAULT_OUT = Path("/dataset/korean_glaucoma_fundus/timeseries_analysis_summary.json")


def analyze(csv_path: Path) -> dict:
    ts = list(csv.DictReader(open(csv_path, encoding="utf-8")))

    visit_counts: dict[int, int] = defaultdict(int)
    patients: dict[str, list[dict]] = defaultdict(list)
    for row in ts:
        pid = row["folder_no"]
        patients[pid].append(row)

    for pid, visits in patients.items():
        visit_counts[len(visits)] += 1

    print("=== 방문 횟수 분포 ===")
    for n in sorted(visit_counts):
        print(f"  {n}회: {visit_counts[n]}명")

    multi = {pid: v for pid, v in patients.items() if len(v) >= 2}
    print(f"\n복수방문: {len(multi)}명")

    changes: dict[str, int] = defaultdict(int)
    for pid, visits in multi.items():
        sorted_v = sorted(visits, key=lambda x: (x.get("visit_idx") or x["date"]))
        for i in range(len(sorted_v) - 1):
            gc = sorted_v[i].get("grade_change", "")
            if gc and gc != "last_visit":
                changes[gc] += 1
    print("Grade 변화:", dict(changes))

    intervals = [
        int(r["days_to_next"])
        for r in ts
        if r.get("days_to_next") and str(r["days_to_next"]).strip() not in ("", "None")
    ]
    avg_interval = sum(intervals) / len(intervals) if intervals else 0.0
    if intervals:
        print(
            f"방문 간격: 평균={avg_interval:.0f}일 "
            f"최소={min(intervals)}일 최대={max(intervals)}일"
        )

    has_vf: set[str] = set()
    has_fundus: set[str] = set()
    for row in ts:
        if row.get("file_vf_R") or row.get("file_vf_L"):
            has_vf.add(row["folder_no"])
        if row.get("file_fundus_R") or row.get("file_fundus_L"):
            has_fundus.add(row["folder_no"])
    both = has_fundus & has_vf
    print(f"\n안저+시야검사 동시 보유: {len(both)}명")
    print(f"안저만: {len(has_fundus - has_vf)}명")

    # 인접 방문 쌍 수 (Phase 1 예상)
    pair_count = 0
    prog_pairs = 0
    for pid, visits in multi.items():
        sorted_v = sorted(visits, key=lambda x: int(x.get("visit_idx") or 0))
        for i in range(len(sorted_v) - 1):
            pair_count += 1
            gc = sorted_v[i].get("grade_change", "")
            if gc == "progression":
                prog_pairs += 1
    print(f"\n인접 방문 쌍(예상): {pair_count}쌍 (progression={prog_pairs})")

    return {
        "total_rows": len(ts),
        "total_patients": len(patients),
        "multi_visit_patients": len(multi),
        "visit_count_distribution": {str(k): v for k, v in sorted(visit_counts.items())},
        "grade_change_transitions": dict(changes),
        "interval_days": {
            "count": len(intervals),
            "avg": avg_interval,
            "min": min(intervals) if intervals else None,
            "max": max(intervals) if intervals else None,
        },
        "modality_overlap": {
            "fundus_and_vf": len(both),
            "fundus_only": len(has_fundus - has_vf),
            "fundus_patients": len(has_fundus),
        },
        "adjacent_pairs": pair_count,
        "progression_pairs": prog_pairs,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    p.add_argument("--output-json", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()

    if not args.csv.is_file():
        print(f"error: missing {args.csv}", file=sys.stderr)
        print("  → python3 scripts/build_timeseries_labels.py", file=sys.stderr)
        sys.exit(1)

    summary = analyze(args.csv)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved: {args.output_json}")


if __name__ == "__main__":
    main()
