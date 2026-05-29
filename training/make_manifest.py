#!/usr/bin/env python3
"""추가 적응증 데이터셋 → 통합 manifest JSON 생성.

예:
  python training/make_manifest.py \\
    --data-root ~/workspace/dataset \\
    --sources refuge,airogs,adam,odir \\
    --output training/manifests/multi_indication.json
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path


def load_refuge(data_root: Path) -> list[dict]:
    """
    REFUGE: 1,200장
    라벨: glaucoma(1)/normal(0) — Glaucoma 폴더명 또는 CSV 기준
    태스크: glaucoma
    """
    base = data_root / "REFUGE_raw"
    samples: list[dict] = []
    if not base.is_dir():
        return samples

    for split_dir in ("Training400", "Validation400", "Test400"):
        split_path = base / split_dir
        if not split_path.is_dir():
            continue
        for img in split_path.rglob("*.jpg"):
            parent_name = img.parent.name.lower()
            if "glaucoma" in parent_name:
                label = 1
            elif "normal" in parent_name:
                label = 0
            else:
                label = 1 if "g" in img.stem.lower() else 0
            samples.append(
                {
                    "path": str(img.relative_to(data_root)),
                    "glaucoma_grade": label,
                    "source": "refuge",
                    "task": "glaucoma",
                }
            )
    return samples


def load_airogs(data_root: Path) -> list[dict]:
    """
    AIROGS: 101,442장
    라벨: RG(1)/NRG(0)
    태스크: glaucoma
    """
    csv_path = data_root / "AIROGS_raw" / "train_labels.csv"
    img_dir = data_root / "AIROGS_raw" / "images"
    samples: list[dict] = []
    if not csv_path.is_file():
        return samples

    with csv_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            img = img_dir / f"{row['challenge_id']}.jpg"
            if img.is_file():
                samples.append(
                    {
                        "path": str(img.relative_to(data_root)),
                        "glaucoma_grade": 1 if row.get("class", "").upper() == "RG" else 0,
                        "source": "airogs",
                        "task": "glaucoma",
                    }
                )
    return samples


def load_adam_amd(data_root: Path) -> list[dict]:
    """
    ADAM: 1,200장
    라벨: AMD(1)/non-AMD(0)
    태스크: amd
    """
    base = data_root / "ADAM_raw"
    samples: list[dict] = []
    if not base.is_dir():
        return samples

    for label, folder in ((1, "AMD"), (0, "Non-AMD")):
        folder_path = base / folder
        if not folder_path.is_dir():
            continue
        for img in folder_path.glob("*.jpg"):
            samples.append(
                {
                    "path": str(img.relative_to(data_root)),
                    "amd_grade": label,
                    "source": "adam",
                    "task": "amd",
                }
            )
    return samples


def load_odir(data_root: Path) -> list[dict]:
    """
    ODIR-2019: 10,000장
    8개 질환 동시 라벨
    태스크: multi
    """
    csv_path = data_root / "ODIR2019_raw" / "labels.csv"
    img_dir = data_root / "ODIR2019_raw" / "images"
    samples: list[dict] = []
    if not csv_path.is_file():
        return samples

    with csv_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            filename = row.get("filename") or row.get("Left-Fundus") or row.get("Right-Fundus")
            if not filename:
                continue
            img = img_dir / filename
            if img.is_file():
                samples.append(
                    {
                        "path": str(img.relative_to(data_root)),
                        "dr_grade": int(row.get("DR", row.get("N", 0)) or 0),
                        "glaucoma_grade": int(row.get("G", 0) or 0),
                        "amd_grade": int(row.get("AMD", 0) or 0),
                        "source": "odir",
                        "task": "multi",
                    }
                )
    return samples


def load_brazil_glaucoma(data_root: Path) -> list[dict]:
    """Brazil Glaucoma 공개 데이터 (논문/ Mendeley)."""
    base = data_root / "BrazilGlaucoma_raw"
    samples: list[dict] = []
    if not base.is_dir():
        return samples

    for label, folder in ((0, "normal"), (1, "glaucoma")):
        folder_path = base / folder
        if not folder_path.is_dir():
            continue
        for ext in ("*.jpg", "*.jpeg", "*.png"):
            for img in folder_path.glob(ext):
                samples.append(
                    {
                        "path": str(img.relative_to(data_root)),
                        "glaucoma_grade": label,
                        "source": "brazil_glaucoma",
                        "task": "glaucoma",
                    }
                )
    return samples


LOADERS = {
    "refuge": load_refuge,
    "airogs": load_airogs,
    "adam": load_adam_amd,
    "odir": load_odir,
    "brazil": load_brazil_glaucoma,
}


def split_samples(
    samples: list[dict],
    *,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
) -> tuple[list[dict], list[dict], list[dict]]:
    rng = random.Random(seed)
    shuffled = samples[:]
    rng.shuffle(shuffled)
    n = len(shuffled)
    n_test = int(n * test_ratio)
    n_val = int(n * val_ratio)
    test = shuffled[:n_test]
    val = shuffled[n_test : n_test + n_val]
    train = shuffled[n_test + n_val :]
    return train, val, test


def main() -> None:
    parser = argparse.ArgumentParser(description="Build multi-indication manifest")
    parser.add_argument("--data-root", type=Path, required=True, help="~/workspace/dataset")
    parser.add_argument(
        "--sources",
        default="refuge,brazil,adam,odir",
        help="쉼표 구분: refuge,airogs,adam,odir,brazil",
    )
    parser.add_argument("--output", type=Path, default=Path("training/manifests/multi_indication.json"))
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--test-ratio", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    data_root = args.data_root.expanduser().resolve()
    sources = [s.strip() for s in args.sources.split(",") if s.strip()]

    all_samples: list[dict] = []
    counts: dict[str, int] = {}
    for name in sources:
        loader = LOADERS.get(name)
        if loader is None:
            raise SystemExit(f"unknown source={name!r}; choose from {sorted(LOADERS)}")
        loaded = loader(data_root)
        counts[name] = len(loaded)
        all_samples.extend(loaded)

    train, val, test = split_samples(
        all_samples,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        seed=args.seed,
    )

    manifest = {
        "data_dir": str(data_root),
        "sources": counts,
        "train": train,
        "val": val,
        "test": test,
    }

    output = args.output if args.output.is_absolute() else Path.cwd() / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"OK {output} total={len(all_samples)} "
        f"train={len(train)} val={len(val)} test={len(test)} sources={counts}"
    )


if __name__ == "__main__":
    main()
