#!/usr/bin/env python3
"""
파일명: scripts/build_timeseries_labels.py
목적:   시계열 라벨 생성 (예후 예측 모델 훈련용)

IRB: 국내 임상기관 IRB 승인 (2019)
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

IRB_INFO = {
    "institution": "Korean Clinical Institution",
    "approved_year": 2019,
    "storage_policy": "LOCAL_ONLY",
    "external_transfer": "PROHIBITED",
    "git_commit": "PROHIBITED",
}

DEFAULT_OUTPUT = Path("/dataset/korean_glaucoma_fundus")


def parse_date(s: str) -> datetime | None:
    try:
        return datetime.strptime(s, "%Y%m%d")
    except ValueError:
        return None


def build_timeseries(output_dir: Path) -> None:
    origin_csv = output_dir / "labels_origin.csv"
    if not origin_csv.exists():
        print(f"error: missing {origin_csv} — run origin preprocessing first", file=sys.stderr)
        sys.exit(1)

    with open(origin_csv, encoding="utf-8") as f:
        records = list(csv.DictReader(f))

    patient_visits: dict[int, dict[str, dict]] = defaultdict(lambda: defaultdict(dict))

    for rec in records:
        folder_no = int(rec["folder_no"])
        date = rec["date"]
        ftype = rec["file_type"]
        mod = rec["modality"]
        eye = rec["eye"]
        fname = rec["filename"]

        key = f"{ftype}_{eye}_{mod}" if ftype != "oct" else "oct"
        patient_visits[folder_no][date][key] = fname

        if "grade" not in patient_visits[folder_no][date]:
            patient_visits[folder_no][date]["grade"] = int(rec.get("grade", 0))
            patient_visits[folder_no][date]["diagnosis"] = rec.get("diagnosis", "")
            patient_visits[folder_no][date]["_unit_no"] = rec.get("_unit_no", "")

    ts_records: list[dict] = []
    multi_visit_count = 0

    for folder_no in sorted(patient_visits.keys()):
        visits = patient_visits[folder_no]
        dates = sorted(visits.keys())
        n_visits = len(dates)

        if n_visits >= 2:
            multi_visit_count += 1

        first_dt = parse_date(dates[0])

        for visit_idx, date in enumerate(dates):
            v = visits[date]
            dt = parse_date(date)
            days_from_first = (dt - first_dt).days if dt and first_dt else 0

            if visit_idx < n_visits - 1:
                next_date = dates[visit_idx + 1]
                next_grade = visits[next_date].get("grade", 0)
                curr_grade = v.get("grade", 0)
                if next_grade > curr_grade:
                    grade_change = "progression"
                elif next_grade < curr_grade:
                    grade_change = "improvement"
                else:
                    grade_change = "stable"
                days_to_next = (
                    (parse_date(next_date) - dt).days
                    if parse_date(next_date) and dt
                    else None
                )
            else:
                grade_change = "last_visit"
                days_to_next = None

            ts_records.append({
                "folder_no": folder_no,
                "visit_idx": visit_idx + 1,
                "date": date,
                "days_from_first": days_from_first,
                "days_to_next": days_to_next,
                "grade": v.get("grade", 0),
                "grade_change": grade_change,
                "file_fundus_R": v.get("fundus_R_color", ""),
                "file_fundus_L": v.get("fundus_L_color", ""),
                "file_vf_R": v.get("vf_R_vf", ""),
                "file_vf_L": v.get("vf_L_vf", ""),
                "file_oct": v.get("oct", ""),
            })

    out_path = output_dir / "timeseries_labels.csv"
    if ts_records:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=ts_records[0].keys())
            writer.writeheader()
            writer.writerows(ts_records)
        print(f"Saved: {out_path} ({len(ts_records)} rows)")

    print()
    print(f"IRB: {IRB_INFO['institution']} ({IRB_INFO['approved_year']})")
    print(f"Multi-visit patients: {multi_visit_count}")

    grade_changes = [r["grade_change"] for r in ts_records if r["grade_change"] != "last_visit"]
    if grade_changes:
        cnt = Counter(grade_changes)
        print(f"  progression:  {cnt.get('progression', 0)}")
        print(f"  stable:       {cnt.get('stable', 0)}")
        print(f"  improvement:  {cnt.get('improvement', 0)}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = p.parse_args()
    build_timeseries(args.output_dir)


if __name__ == "__main__":
    main()
