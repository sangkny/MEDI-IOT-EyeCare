#!/usr/bin/env python3
"""QC evaluation script — provisional thresholds; not clinical validation.

Outputs CSV-ish lines: filename, data_source, metrics, status, reasons
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.clinical_image_qc import run_clinical_image_qc  # noqa: E402


def main(paths: list[str]) -> int:
    print("filename\tdata_source\tqc_status\tlaplacian\tbrightness\tfov\treasons")
    for p in paths:
        path = Path(p)
        data = path.read_bytes()
        # heuristic category
        src = "SYNTHETIC/SAMPLE"
        if "EyePACS" in str(path) or "real" in str(path).lower():
            src = "REAL_OR_PUBLIC"
        qc = run_clinical_image_qc(data, filename=path.name)
        m = qc.get("qc_metrics") or {}
        print(
            f"{path.name}\t{src}\t{qc['qc_status']}\t"
            f"{m.get('laplacian_var')}\t{m.get('brightness_mean')}\t{m.get('fov_coverage')}\t"
            f"{';'.join(qc.get('qc_reasons') or [])}"
        )
    print(
        "# NOTE: thresholds are PROVISIONAL / SYNTHETIC-DATA-DERIVED — not clinically validated"
    )
    return 0


if __name__ == "__main__":
    args = sys.argv[1:] or [
        str(ROOT / "data/synthetic/images/test/0/g0_0000.jpg"),
    ]
    raise SystemExit(main(args))
