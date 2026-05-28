#!/usr/bin/env python3
"""EyeQ Good(quality=0) + unified_v4 → unified_eyeq_good.json."""
import csv
import json
import random
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EYEQ_CSV = ROOT / "data" / "EyePACS_raw" / "Label_EyeQ_train.csv"
EYEPACS_LABELS = ROOT / "data" / "EyePACS_raw" / "trainLabels.csv"
EYEPACS_IMG_DIR = Path(
    "/home/smartvisionglobal/workspace/dataset/EyePACS_raw/train"
)
V4_MANIFEST = ROOT / "training" / "manifests" / "unified_v4.json"
OUT_MANIFEST = ROOT / "training" / "manifests" / "unified_eyeq_good.json"


def _good_image_ids():
    good = set()
    with EYEQ_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if str(row.get("quality", "")).strip() != "0":
                continue
            name = (row.get("image") or "").strip()
            if not name:
                continue
            good.add(name.replace(".jpeg", ""))
    return good


def _eyepacs_good_samples(good_ids):
    out = []
    if not EYEPACS_LABELS.is_file():
        raise FileNotFoundError(EYEPACS_LABELS)
    with EYEPACS_LABELS.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            img_id = (row.get("image") or "").strip()
            if not img_id or img_id not in good_ids:
                continue
            img_path = EYEPACS_IMG_DIR / f"{img_id}.jpeg"
            if not img_path.is_file():
                continue
            out.append(
                {
                    "path": f"/dataset/EyePACS_raw/train/{img_id}.jpeg",
                    "dr_grade": int(row["level"]),
                    "source": "eyepacs_good",
                }
            )
    return out


def _v4_samples():
    with V4_MANIFEST.open(encoding="utf-8") as f:
        data = json.load(f)
    base = data.get("data_dir", "data")
    out = []
    for split in ("train", "val", "test"):
        for s in data.get(split, []):
            rel = s["path"]
            rel_path = f"{base}/{rel}" if not str(rel).startswith(f"{base}/") else rel
            out.append(
                {
                    "path": str(rel_path),
                    "dr_grade": int(s["dr_grade"]),
                    "source": "v4",
                }
            )
    return out


def main():
    random.seed(42)
    good_ids = _good_image_ids()
    print(f"EyeQ Good IDs: {len(good_ids)}")

    eyepacs = _eyepacs_good_samples(good_ids)
    print(f"EyePACS Good matched files: {len(eyepacs)}")
    print(
        "EyePACS grade dist:",
        dict(sorted(Counter(s["dr_grade"] for s in eyepacs).items())),
    )

    v4 = _v4_samples()
    print(f"v4 samples: {len(v4)}")

    all_samples = eyepacs + v4
    random.shuffle(all_samples)
    total = len(all_samples)
    for i, s in enumerate(all_samples):
        if i < int(total * 0.8):
            s["split"] = "train"
        elif i < int(total * 0.9):
            s["split"] = "val"
        else:
            s["split"] = "test"

    print(f"\nTotal: {total}")
    print("Source:", dict(Counter(s["source"] for s in all_samples)))
    print(
        "Grade:",
        dict(sorted(Counter(s["dr_grade"] for s in all_samples).items())),
    )

    output = {
        "data_dir": ".",
        "meta": {
            "datasets": ["eyepacs_good", "aptos", "messidor2", "idrid"],
            "total": total,
            "eyeq_filter": "Good only (quality=0)",
            "eyepacs_good_matched": len(eyepacs),
            "v4_count": len(v4),
        },
        "train": [
            {"path": s["path"], "dr_grade": s["dr_grade"]}
            for s in all_samples
            if s["split"] == "train"
        ],
        "val": [
            {"path": s["path"], "dr_grade": s["dr_grade"]}
            for s in all_samples
            if s["split"] == "val"
        ],
        "test": [
            {"path": s["path"], "dr_grade": s["dr_grade"]}
            for s in all_samples
            if s["split"] == "test"
        ],
    }

    OUT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with OUT_MANIFEST.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nOK {OUT_MANIFEST}")
    print(f"  train: {len(output['train'])}")
    print(f"  val:   {len(output['val'])}")
    print(f"  test:  {len(output['test'])}")


if __name__ == "__main__":
    main()
