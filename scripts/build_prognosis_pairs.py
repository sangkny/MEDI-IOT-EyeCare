#!/usr/bin/env python3
"""
파일명: scripts/build_prognosis_pairs.py
목적:   timeseries_labels.csv → prognosis_pairs.csv (인접 방문 쌍)

IRB: 국내 임상기관 IRB 승인 (2019) — 로컬 전용
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_ROOT = Path("/dataset/korean_glaucoma_fundus")
DEFAULT_TS = DEFAULT_ROOT / "timeseries_labels.csv"
DEFAULT_OUT = DEFAULT_ROOT / "prognosis_pairs.csv"
DEFAULT_ORIGIN_CSV = DEFAULT_ROOT / "labels_origin.csv"


def _fundus_path(root: Path, fname: str, eye: str) -> Path:
    sub = "OD" if eye == "R" else "OS"
    return root / "origin" / "fundus" / sub / fname


def load_folder_meta(origin_csv: Path) -> dict[int, dict]:
    meta: dict[int, dict] = {}
    if not origin_csv.is_file():
        return meta
    with open(origin_csv, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            fn = int(row["folder_no"])
            if fn in meta:
                continue
            diag = row.get("diagnosis", "") or ""
            is_ntg = int(row.get("is_ntg", 0) or 0)
            if not is_ntg and "NTG" in diag.upper():
                is_ntg = 1
            meta[fn] = {"diagnosis": diag, "is_ntg": is_ntg}
    return meta


def build_pairs(
    ts_csv: Path,
    output_csv: Path,
    *,
    data_root: Path,
    origin_csv: Path,
    require_bilateral: bool = True,
) -> list[dict]:
    rows = list(csv.DictReader(open(ts_csv, encoding="utf-8")))
    by_patient: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_patient[row["folder_no"]].append(row)

    meta = load_folder_meta(origin_csv)
    pairs: list[dict] = []

    for folder_no, visits in sorted(by_patient.items(), key=lambda x: int(x[0])):
        sorted_v = sorted(visits, key=lambda x: int(x.get("visit_idx") or 0))
        for i in range(len(sorted_v) - 1):
            vi, vj = sorted_v[i], sorted_v[i + 1]
            fr_i = (vi.get("file_fundus_R") or "").strip()
            fl_i = (vi.get("file_fundus_L") or "").strip()
            fr_j = (vj.get("file_fundus_R") or "").strip()
            fl_j = (vj.get("file_fundus_L") or "").strip()

            path_fr_i = _fundus_path(data_root, fr_i, "R") if fr_i else None
            path_fl_i = _fundus_path(data_root, fl_i, "L") if fl_i else None
            path_fr_j = _fundus_path(data_root, fr_j, "R") if fr_j else None
            path_fl_j = _fundus_path(data_root, fl_j, "L") if fl_j else None

            if require_bilateral:
                if not path_fr_i or not path_fl_i:
                    continue
                if not path_fr_i.is_file() or not path_fl_i.is_file():
                    continue
            else:
                if not ((path_fr_i and path_fr_i.is_file()) or (path_fl_i and path_fl_i.is_file())):
                    continue

            grade_change = vi.get("grade_change", "stable")
            if grade_change == "last_visit":
                continue
            label = 1 if grade_change == "progression" else 0

            days_raw = vi.get("days_to_next")
            days_interval = int(days_raw) if days_raw not in (None, "", "None") else 0

            fn = int(folder_no)
            pm = meta.get(fn, {"diagnosis": "", "is_ntg": 0})

            pairs.append({
                "folder_no": folder_no,
                "visit_i": vi.get("visit_idx", i + 1),
                "visit_j": vj.get("visit_idx", i + 2),
                "date_i": vi.get("date", ""),
                "date_j": vj.get("date", ""),
                "fundus_R_i": fr_i,
                "fundus_L_i": fl_i,
                "fundus_R_j": fr_j,
                "fundus_L_j": fl_j,
                "path_fundus_R_i": str(path_fr_i) if path_fr_i else "",
                "path_fundus_L_i": str(path_fl_i) if path_fl_i else "",
                "grade_i": int(vi.get("grade") or 0),
                "grade_j": int(vj.get("grade") or 0),
                "grade_change": grade_change,
                "days_interval": days_interval,
                "is_ntg": pm["is_ntg"],
                "diagnosis": pm["diagnosis"],
                "label": label,
            })

    if not pairs:
        print("WARN: no valid pairs generated", file=sys.stderr)
        return pairs

    fieldnames = list(pairs[0].keys())
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(pairs)

    labels = Counter(p["label"] for p in pairs)
    ntg = Counter(p["is_ntg"] for p in pairs)
    print(f"OK {output_csv}")
    print(f"  total pairs: {len(pairs)}")
    print(f"  progression=1: {labels.get(1, 0)} ({labels.get(1, 0) / len(pairs) * 100:.1f}%)")
    print(f"  stable/improvement=0: {labels.get(0, 0)}")
    print(f"  NTG pairs: {ntg.get(1, 0)} · non-NTG: {ntg.get(0, 0)}")
    return pairs


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--timeseries-csv", type=Path, default=DEFAULT_TS)
    p.add_argument("--output", type=Path, default=DEFAULT_OUT)
    p.add_argument("--data-root", type=Path, default=DEFAULT_ROOT)
    p.add_argument("--origin-csv", type=Path, default=DEFAULT_ORIGIN_CSV)
    p.add_argument("--allow-unilateral", action="store_true")
    args = p.parse_args()

    if not args.timeseries_csv.is_file():
        print(f"error: missing {args.timeseries_csv}", file=sys.stderr)
        sys.exit(1)

    build_pairs(
        args.timeseries_csv,
        args.output,
        data_root=args.data_root,
        origin_csv=args.origin_csv,
        require_bilateral=not args.allow_unilateral,
    )


if __name__ == "__main__":
    main()
