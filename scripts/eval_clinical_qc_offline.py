#!/usr/bin/env python3
"""Offline QC evaluation tool — ready for future real-fundus validation.

Usage:
  PYTHONPATH=. python scripts/eval_clinical_qc_offline.py --dir /path/to/images
  PYTHONPATH=. python scripts/eval_clinical_qc_offline.py --manifest labels.csv

Manifest CSV columns (optional):
  path,image_id,source,human_quality,human_reason

No PHI. Do not commit real patient images to Git.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.clinical_image_qc import QC_VERSION, run_clinical_image_qc  # noqa: E402


def _iter_images(directory: Path):
    for p in sorted(directory.rglob("*")):
        if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}:
            yield p


def _row_from_path(path: Path, *, source: str, image_id: str | None, human_quality: str | None, human_reason: str | None):
    data = path.read_bytes()
    qc = run_clinical_image_qc(data, filename=path.name)
    feats = (qc.get("qc_features") or {}).get("scores") or {}
    return {
        "image_id": image_id or path.stem,
        "source": source,
        "path": str(path),
        "qc_version": qc.get("qc_version") or QC_VERSION,
        "qc_feature_version": qc.get("qc_feature_version"),
        "qc_status": qc.get("qc_status"),
        "qc_reasons": ";".join(qc.get("qc_reasons") or []),
        "qc_metrics": json.dumps(qc.get("qc_metrics") or {}, ensure_ascii=False),
        "qc_feature_scores": json.dumps(feats, ensure_ascii=False),
        "human_quality": human_quality or "",
        "human_reason": human_reason or "",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=str, help="directory of images")
    ap.add_argument("--manifest", type=str, help="CSV manifest")
    ap.add_argument("--out", type=str, default="-", help="output CSV path or - for stdout")
    args = ap.parse_args()

    rows = []
    if args.manifest:
        with open(args.manifest, newline="", encoding="utf-8") as f:
            for rec in csv.DictReader(f):
                path = Path(rec["path"])
                rows.append(
                    _row_from_path(
                        path,
                        source=rec.get("source") or "UNKNOWN",
                        image_id=rec.get("image_id"),
                        human_quality=rec.get("human_quality"),
                        human_reason=rec.get("human_reason"),
                    )
                )
    elif args.dir:
        for path in _iter_images(Path(args.dir)):
            rows.append(
                _row_from_path(
                    path,
                    source="SYNTHETIC/SAMPLE_OR_LOCAL",
                    image_id=None,
                    human_quality=None,
                    human_reason=None,
                )
            )
    else:
        ap.error("provide --dir or --manifest")

    fieldnames = list(rows[0].keys()) if rows else [
        "image_id",
        "source",
        "path",
        "qc_version",
        "qc_feature_version",
        "qc_status",
        "qc_reasons",
        "qc_metrics",
        "qc_feature_scores",
        "human_quality",
        "human_reason",
    ]
    out_f = sys.stdout if args.out == "-" else open(args.out, "w", newline="", encoding="utf-8")
    try:
        w = csv.DictWriter(out_f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    finally:
        if out_f is not sys.stdout:
            out_f.close()
    print(
        f"# rows={len(rows)} qc_version={QC_VERSION} "
        f"(thresholds unchanged; features are non-gating)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
